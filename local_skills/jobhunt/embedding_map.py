#!/usr/bin/env python3
"""Compute 2D embedding map of job opportunities for the dashboard.

Reads opportunity notes from TypeDB, embeds via Voyage AI, stores in Qdrant,
and runs PyMDE to produce 2D coordinates for visualization.

Usage:
    # Compute embeddings and store in Qdrant (run after sensemaking)
    uv run python local_skills/jobhunt/embedding_map.py embed

    # Get 2D map coordinates (fast — reads from Qdrant, runs PyMDE)
    uv run python local_skills/jobhunt/embedding_map.py map [--exclude id1 id2 ...]

    # Both: embed then map
    uv run python local_skills/jobhunt/embedding_map.py embed-and-map
"""
import argparse
import json
import os
import sys
import time

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION = "jobhunt-opportunities"
VECTOR_DIM = 1024  # voyage-4-large


def get_typedb_driver():
    from typedb.driver import Credentials, DriverOptions, TypeDB
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials("admin", "password"),
        DriverOptions(is_tls_enabled=False),
    )


def get_qdrant_client():
    from qdrant_client import QdrantClient
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection():
    """Create Qdrant collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION not in collections:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection: {COLLECTION}", file=sys.stderr)
    return client


def fetch_opportunities():
    """Fetch all opportunities with their sensemaking notes from TypeDB."""
    from typedb.driver import TransactionType

    driver = get_typedb_driver()
    opportunities = []

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        # Get all opportunity subtypes
        for otype in ["jhunt-position", "jhunt-engagement", "jhunt-venture", "jhunt-lead"]:
            type_label = otype.replace("jhunt-", "")
            opps = list(tx.query(f'''match $o isa {otype}, has id $id, has name $n;
                fetch {{ "id": $id, "name": $n }};''').resolve())

            for opp in opps:
                oid = opp["id"]
                oname = opp["name"]

                # Get jhunt-short-name, priority, created-at
                extras = {}
                for attr in ["jhunt-short-name", "jhunt-priority-level", "created-at"]:
                    try:
                        r = list(tx.query(f'''match $o isa {otype}, has id "{oid}", has {attr} $v;
                            fetch {{ "v": $v }};''').resolve())
                        if r:
                            extras[attr] = r[0]["v"]
                    except:
                        pass

                # Get status: jhunt-application-status from note (positions) or jhunt-opportunity-status from entity
                try:
                    if otype == "jhunt-position":
                        status_r = list(tx.query(f'''match
                            $o isa {otype}, has id "{oid}";
                            (note: $n, subject: $o) isa alh-aboutness;
                            $n isa jhunt-application-note, has jhunt-application-status $s;
                        fetch {{ "status": $s }};''').resolve())
                        if status_r:
                            extras["status"] = status_r[0]["status"]
                    else:
                        status_r = list(tx.query(f'''match
                            $o isa {otype}, has id "{oid}", has jhunt-opportunity-status $s;
                        fetch {{ "status": $s }};''').resolve())
                        if status_r:
                            extras["status"] = status_r[0]["status"]
                except:
                    pass

                # Get company
                company = None
                try:
                    for rel, my_role, co_role in [
                        ("jhunt-position-at-company", "position", "employer"),
                        ("jhunt-opportunity-at-organization", "opportunity", "organization"),
                    ]:
                        co_r = list(tx.query(f'''match
                            $o isa {otype}, has id "{oid}";
                            ({my_role}: $o, {co_role}: $c) isa {rel};
                        fetch {{ "company": $c.name }};''').resolve())
                        if co_r:
                            company = co_r[0]["company"]
                            break
                except:
                    pass

                # Prefer opp-summary note; fall back to other sensemaking notes
                summary_text = None
                try:
                    summary_r = list(tx.query(f'''match
                        $o isa {otype}, has id "{oid}";
                        (note: $n, subject: $o) isa alh-aboutness;
                        $n isa jhunt-opp-summary-note, has content $c;
                    fetch {{ "content": $c }};''').resolve())
                    if summary_r:
                        summary_text = summary_r[0]["content"]
                except:
                    pass

                notes_text = []
                if not summary_text:
                    for ntype in ["jhunt-research-note", "jhunt-fit-analysis-note",
                                  "jhunt-strategy-note", "jhunt-skill-gap-note", "note"]:
                        try:
                            notes = list(tx.query(f'''match
                                $o isa {otype}, has id "{oid}";
                                (note: $n, subject: $o) isa alh-aboutness;
                                $n isa {ntype}, has content $c;
                            fetch {{ "content": $c }};''').resolve())
                            for n in notes:
                                if n.get("content"):
                                    notes_text.append(n["content"])
                        except:
                            pass

                # Build the text to embed
                embed_text = f"Title: {oname}\n"
                if company:
                    embed_text += f"Company: {company}\n"
                embed_text += f"Type: {type_label}\n"
                if summary_text:
                    embed_text += summary_text
                elif notes_text:
                    embed_text += "\n".join(notes_text)
                else:
                    embed_text += f"No sensemaking notes yet for this {type_label}."

                opportunities.append({
                    "id": oid,
                    "name": oname,
                    "short_name": extras.get("jhunt-short-name", oname[:30]),
                    "type": type_label,
                    "status": extras.get("status"),
                    "priority": extras.get("jhunt-priority-level"),
                    "company": company,
                    "created_at": str(extras.get("created-at", "")) or None,
                    "text": embed_text,
                })

    driver.close()
    return opportunities


def cmd_embed(args):
    """Compute embeddings and store in Qdrant."""
    from skillful_alhazen.utils.embeddings import embed_texts
    from qdrant_client.models import PointStruct

    print("Fetching opportunities from TypeDB...", file=sys.stderr)
    opportunities = fetch_opportunities()
    print(f"Found {len(opportunities)} opportunities", file=sys.stderr)

    if not opportunities:
        print(json.dumps({"success": True, "count": 0}))
        return

    # Compute embeddings
    texts = [o["text"] for o in opportunities]
    print(f"Embedding {len(texts)} texts via Voyage AI...", file=sys.stderr)
    embeddings = embed_texts(texts, input_type="document")
    print(f"Got {len(embeddings)} embeddings", file=sys.stderr)

    # Store in Qdrant
    client = ensure_collection()
    points = []
    for i, (opp, emb) in enumerate(zip(opportunities, embeddings)):
        points.append(PointStruct(
            id=i,
            vector=emb,
            payload={
                "opp_id": opp["id"],
            },
        ))

    # Upsert (recreate collection to avoid stale points)
    from qdrant_client.models import Distance, VectorParams
    try:
        client.delete_collection(COLLECTION)
    except:
        pass
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"Stored {len(points)} embeddings in Qdrant collection '{COLLECTION}'", file=sys.stderr)

    print(json.dumps({"success": True, "count": len(points)}))


def cmd_map(args):
    """Get 2D map coordinates from stored embeddings."""
    import numpy as np

    client = get_qdrant_client()

    # Fetch all points from Qdrant
    points = client.scroll(collection_name=COLLECTION, limit=10000, with_vectors=True)[0]

    if not points:
        print(json.dumps({"success": True, "items": [], "count": 0}))
        return

    # Apply exclusions
    exclude_set = set(args.exclude or [])
    filtered = [p for p in points if p.payload["opp_id"] not in exclude_set]

    if len(filtered) < 3:
        # Too few points for PyMDE — return as-is with random positions
        items = []
        for i, p in enumerate(filtered):
            items.append({
                **p.payload,
                "id": p.payload["opp_id"],
                "x": float(i),
                "y": 0.0,
            })
        print(json.dumps({"success": True, "items": items, "count": len(items)}))
        return

    # Load seed coordinates from TypeDB dashboard state note
    seed_coords = {}
    try:
        from typedb.driver import TransactionType as TxType
        tdb = get_typedb_driver()
        with tdb.transaction(TYPEDB_DATABASE, TxType.READ) as tx_read:
            states = list(tx_read.query('''match
                $n isa jhunt-dashboard-state-note, has content $c, has name "embedding-map-coordinates";
            fetch { "content": $c };''').resolve())
            if states:
                cached = json.loads(states[0]["content"])
                seed_coords = {k: (v["x"], v["y"]) for k, v in cached.items()}
        tdb.close()
    except Exception:
        pass

    # Extract vectors and run PyMDE
    import pymde
    import torch

    vectors = np.array([p.vector for p in filtered])
    tensor = torch.FloatTensor(vectors)

    # Build initial embedding from cached positions (if available)
    init = None
    if seed_coords:
        init_list = []
        has_seed = True
        for p in filtered:
            oid = p.payload["opp_id"]
            if oid in seed_coords:
                init_list.append(seed_coords[oid])
            else:
                has_seed = False
                break
        if has_seed and len(init_list) == len(filtered):
            init = torch.FloatTensor(init_list)

    mde = pymde.preserve_neighbors(
        tensor,
        embedding_dim=2,
        constraint=pymde.Standardized(),
        repulsive_fraction=0.7,
        n_neighbors=min(5, len(filtered) - 1),
        init="quadratic",
    )
    # Use cached seed positions as starting point if available
    if init is not None:
        embedding_2d = mde.embed(X=init).cpu().numpy()
    else:
        embedding_2d = mde.embed().cpu().numpy()

    # Build ID → 2D coordinate map
    coord_by_id = {}
    for i, p in enumerate(filtered):
        coord_by_id[p.payload["opp_id"]] = {
            "x": float(embedding_2d[i, 0]),
            "y": float(embedding_2d[i, 1]),
        }

    # Fetch FRESH metadata from TypeDB (not stale Qdrant payloads)
    from typedb.driver import TransactionType as TxType
    tdb_meta = get_typedb_driver()
    metadata = {}
    with tdb_meta.transaction(TYPEDB_DATABASE, TxType.READ) as tx_m:
        for otype in ["jhunt-position", "jhunt-engagement", "jhunt-venture", "jhunt-lead"]:
            type_label = otype.replace("jhunt-", "")
            opps = list(tx_m.query(f'''match $o isa {otype}, has id $id, has name $n;
                fetch {{ "id": $id, "name": $n }};''').resolve())
            for opp in opps:
                oid = opp["id"]
                if oid not in coord_by_id:
                    continue
                meta = {"id": oid, "name": opp["name"], "type": type_label}
                # Fetch optional attributes
                for attr, key in [("jhunt-short-name", "short_name"), ("jhunt-priority-level", "priority"), ("created-at", "created_at")]:
                    try:
                        r = list(tx_m.query(f'match $o isa {otype}, has id "{oid}", has {attr} $v; fetch {{ "v": $v }};').resolve())
                        if r:
                            meta[key] = str(r[0]["v"]) if attr == "created-at" else r[0]["v"]
                    except:
                        pass
                # Status: jhunt-application-status from note (positions) or jhunt-opportunity-status from entity
                try:
                    if otype == "jhunt-position":
                        s = list(tx_m.query(f'''match $o isa {otype}, has id "{oid}";
                            (note: $n, subject: $o) isa alh-aboutness;
                            $n isa jhunt-application-note, has jhunt-application-status $s;
                        fetch {{ "s": $s }};''').resolve())
                        if s:
                            meta["status"] = s[0]["s"]
                    else:
                        s = list(tx_m.query(f'''match $o isa {otype}, has id "{oid}", has jhunt-opportunity-status $s;
                        fetch {{ "s": $s }};''').resolve())
                        if s:
                            meta["status"] = s[0]["s"]
                except:
                    pass
                # Company
                try:
                    for rel, my_role, co_role in [
                        ("jhunt-position-at-company", "position", "employer"),
                        ("jhunt-opportunity-at-organization", "opportunity", "organization"),
                    ]:
                        co = list(tx_m.query(f'''match $o isa {otype}, has id "{oid}";
                            ({my_role}: $o, {co_role}: $c) isa {rel};
                        fetch {{ "c": $c.name }};''').resolve())
                        if co:
                            meta["company"] = co[0]["c"]
                            break
                except:
                    pass
                # Opp summary note
                try:
                    sm = list(tx_m.query(f'''match $o isa {otype}, has id "{oid}";
                        (note: $n, subject: $o) isa alh-aboutness;
                        $n isa jhunt-opp-summary-note, has content $c;
                    fetch {{ "c": $c }};''').resolve())
                    if sm:
                        meta["summary_text"] = sm[0]["c"]
                except:
                    pass
                metadata[oid] = meta
    tdb_meta.close()

    # Join coordinates with fresh metadata
    items = []
    for oid, coords in coord_by_id.items():
        meta = metadata.get(oid, {"id": oid, "name": oid, "type": "unknown"})
        items.append({
            **meta,
            "short_name": meta.get("short_name", meta.get("name", oid)[:30]),
            "status": meta.get("status"),
            "priority": meta.get("priority"),
            "company": meta.get("company"),
            "created_at": meta.get("created_at"),
            "summary_text": meta.get("summary_text"),
            "x": coords["x"],
            "y": coords["y"],
        })

    result = {"success": True, "items": items, "count": len(items)}

    # Save coordinates to TypeDB dashboard state note
    try:
        from typedb.driver import TransactionType as TxType
        cache = {item["id"]: {"x": item["x"], "y": item["y"]} for item in items}
        cache_json = json.dumps(cache).replace('"', '\\"')
        tdb = get_typedb_driver()
        # Delete old state note if exists
        with tdb.transaction(TYPEDB_DATABASE, TxType.WRITE) as tx_w:
            try:
                tx_w.query('match $n isa jhunt-dashboard-state-note, has name "embedding-map-coordinates"; delete $n;').resolve()
            except Exception:
                pass
            tx_w.commit()
        # Insert new state note
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        with tdb.transaction(TYPEDB_DATABASE, TxType.WRITE) as tx_w:
            tx_w.query(f'''insert $n isa jhunt-dashboard-state-note,
                has id "dashboard-state-embedding-map",
                has name "embedding-map-coordinates",
                has content "{cache_json}",
                has created-at {timestamp};''').resolve()
            tx_w.commit()
        tdb.close()
    except Exception as e:
        print(f"Warning: could not save state to TypeDB: {e}", file=sys.stderr)

    print(json.dumps(result, default=str))


def cmd_embed_and_map(args):
    """Embed then map in one shot."""
    cmd_embed(args)
    cmd_map(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jobhunt opportunity embedding map")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("embed", help="Compute embeddings and store in Qdrant")

    p_map = sub.add_parser("map", help="Get 2D map coordinates")
    p_map.add_argument("--exclude", nargs="*", help="Opportunity IDs to exclude")
    p_map.add_argument("--seed-file", help="Path to JSON file with seed coordinates {id: {x, y}}")

    p_both = sub.add_parser("embed-and-map", help="Embed then map")
    p_both.add_argument("--exclude", nargs="*", help="Opportunity IDs to exclude")

    args = parser.parse_args()
    if args.command == "embed":
        cmd_embed(args)
    elif args.command == "map":
        cmd_map(args)
    elif args.command == "embed-and-map":
        cmd_embed_and_map(args)
    else:
        parser.print_help()


# =============================================================================
# Candidate embedding helpers (called from job_forager.py)
# =============================================================================

CANDIDATES_COLLECTION = "jobhunt-candidates"


def _ensure_candidates_collection():
    """Create the candidates Qdrant collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    if CANDIDATES_COLLECTION not in collections:
        client.create_collection(
            collection_name=CANDIDATES_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
    return client


def embed_and_upsert_candidate(candidate_id: str, text: str):
    """Embed a candidate's text and upsert into Qdrant."""
    from skillful_alhazen.utils.embeddings import embed_texts
    from qdrant_client.models import PointStruct
    import hashlib

    embeddings = embed_texts([text], input_type="document")
    if not embeddings:
        return

    client = _ensure_candidates_collection()
    # Use a numeric hash of the ID as the Qdrant point ID
    point_id = int(hashlib.md5(candidate_id.encode()).hexdigest()[:15], 16)
    client.upsert(
        collection_name=CANDIDATES_COLLECTION,
        points=[PointStruct(
            id=point_id,
            vector=embeddings[0],
            payload={"candidate_id": candidate_id, "text": text},
        )],
    )


def search_candidates_semantic(query: str, limit: int = 10) -> list[dict]:
    """Semantic search across candidate embeddings."""
    from skillful_alhazen.utils.embeddings import embed_texts

    embeddings = embed_texts([query], input_type="query")
    if not embeddings:
        return []

    client = _ensure_candidates_collection()
    results = client.query_points(
        collection_name=CANDIDATES_COLLECTION,
        query=embeddings[0],
        limit=limit,
    ).points

    return [
        {
            "candidate_id": r.payload.get("candidate_id", ""),
            "text": r.payload.get("text", ""),
            "score": r.score,
        }
        for r in results
    ]
