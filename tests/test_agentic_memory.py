"""
Tests for the agentic-memory skill CLI.

These tests require a running TypeDB instance with the alhazen_notebook database.
To run:
    1. Start TypeDB: make db-start
    2. Run tests: pytest tests/test_agentic_memory.py -v

For CI, use pytest markers to skip if TypeDB is not available.
"""

import json
import os
import subprocess
import socket
import uuid

import pytest

# Skip all tests if typedb-driver is not installed
pytest.importorskip("typedb.driver")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(PROJECT_ROOT, "skills", "agentic-memory", "agentic_memory.py")

ENV = {
    **os.environ,
    "TYPEDB_DATABASE": "alhazen_notebook",
}

# Known entities in the live database
OPERATOR_ID = "op-f25ab4b15b0f"
KNOWN_EPISODE_ID = "ep-1ebcef739bfe"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(*args: str, expect_success: bool = True) -> dict:
    """Run an agentic_memory.py command and return parsed JSON output."""
    result = subprocess.run(
        ["uv", "run", "python", SCRIPT, *args],
        capture_output=True,
        text=True,
        env=ENV,
        cwd=PROJECT_ROOT,
    )
    # Parse stdout (ignore stderr warnings)
    assert result.stdout.strip(), (
        f"No stdout from command: {args}\nstderr: {result.stderr[:500]}"
    )
    data = json.loads(result.stdout)
    if expect_success:
        assert data.get("success") is True, f"Command failed: {data}"
    return data


def typedb_available() -> bool:
    """Check if TypeDB server is running."""
    try:
        from typedb.driver import TypeDB, Credentials, DriverOptions
        driver = TypeDB.driver(
            "localhost:1729",
            Credentials("admin", "password"),
            DriverOptions(is_tls_enabled=False),
        )
        driver.close()
        return True
    except Exception:
        return False


def qdrant_available() -> bool:
    """Check if Qdrant is reachable on localhost:6333."""
    try:
        sock = socket.create_connection(("localhost", 6333), timeout=2)
        sock.close()
        return True
    except (OSError, socket.timeout):
        return False


# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

requires_typedb = pytest.mark.skipif(
    not typedb_available(),
    reason="TypeDB server not available at localhost:1729",
)

requires_qdrant = pytest.mark.skipif(
    not qdrant_available(),
    reason="Qdrant not available at localhost:6333",
)

requires_voyage = pytest.mark.skipif(
    not os.getenv("VOYAGE_API_KEY"),
    reason="VOYAGE_API_KEY not set",
)


# ---------------------------------------------------------------------------
# A. Schema Introspection
# ---------------------------------------------------------------------------

class TestSchemaIntrospection:
    """Tests for the describe-schema command."""

    @requires_typedb
    def test_describe_schema_live_default(self):
        """describe-schema returns entities, relations, and embedding_index."""
        data = run_cmd("describe-schema")
        assert data["source"] == "live"
        assert "entities" in data
        assert "relations" in data
        assert "embedding_index" in data
        # Core entity types must be present
        assert "nbmem-operator-user" in data["entities"]
        assert "alh-episode" in data["entities"]

    @requires_typedb
    def test_describe_schema_live_skill_filter(self):
        """describe-schema --skill jobhunt filters to jobhunt + core types."""
        data = run_cmd("describe-schema", "--skill", "jobhunt")
        entities = data["entities"]
        # Core types should still be present
        assert "nbmem-operator-user" in entities
        # If any jobhunt types exist, they should start with 'jobhunt-'
        jobhunt_types = [k for k in entities if k.startswith("jobhunt-")]
        # At least some jobhunt types expected (position, company, etc.)
        assert len(jobhunt_types) > 0, "Expected jobhunt namespace types"

    @requires_typedb
    def test_describe_schema_live_full(self):
        """describe-schema --full includes instance counts."""
        data = run_cmd("describe-schema", "--full")
        # Pick a type that has known instances
        if "nbmem-operator-user" in data["entities"]:
            entry = data["entities"]["nbmem-operator-user"]
            assert "instance_count" in entry
            assert isinstance(entry["instance_count"], int)

    @requires_typedb
    def test_describe_schema_files_source(self):
        """describe-schema --source files parses .tql files instead of live DB."""
        data = run_cmd("describe-schema", "--source", "files")
        assert data["source"] == "files"
        assert "entities" in data
        assert "relations" in data

    @requires_typedb
    def test_describe_schema_entities_have_parent(self):
        """Entity entries include parent in the hierarchy."""
        data = run_cmd("describe-schema")
        ep = data["entities"].get("alh-episode")
        assert ep is not None
        assert "parent" in ep

    @requires_typedb
    def test_describe_schema_relations_have_roles(self):
        """Relation entries include role lists."""
        data = run_cmd("describe-schema")
        # aboutness should have note and subject roles
        aboutness = data["relations"].get("alh-aboutness")
        assert aboutness is not None
        assert "roles" in aboutness
        assert len(aboutness["roles"]) >= 2


# ---------------------------------------------------------------------------
# B. Query Interface
# ---------------------------------------------------------------------------

class TestQueryInterface:
    """Tests for the query command (read and write mode)."""

    @requires_typedb
    def test_query_read_fetch(self):
        """query --typeql with a fetch returns structured results."""
        typeql = (
            f'match $p isa nbmem-operator-user, has id "{OPERATOR_ID}"; '
            'fetch { "id": $p.id, "name": $p.name };'
        )
        data = run_cmd("query", "--typeql", typeql)
        assert data["count"] >= 1
        row = data["results"][0]
        assert row["id"] == OPERATOR_ID

    @requires_typedb
    def test_query_read_with_limit(self):
        """query --limit restricts result count."""
        typeql = 'match $n isa alh-note; fetch { "id": $n.id };'
        data = run_cmd("query", "--typeql", typeql, "--limit", "3")
        assert data["count"] <= 3

    @requires_typedb
    def test_query_read_no_results(self):
        """query that matches nothing returns count 0."""
        typeql = (
            'match $p isa nbmem-operator-user, has id "nonexistent-id-xyz"; '
            'fetch { "id": $p.id };'
        )
        data = run_cmd("query", "--typeql", typeql)
        assert data["count"] == 0
        assert data["results"] == []

    @requires_typedb
    def test_query_invalid_typeql(self):
        """query with bad TypeQL returns success=false."""
        data = run_cmd(
            "query", "--typeql", "this is not valid typeql;",
            expect_success=False,
        )
        assert data["success"] is False
        assert "error" in data

    @requires_typedb
    def test_query_count_collections(self):
        """query can count collections in the database."""
        typeql = 'match $c isa alh-collection; fetch { "id": $c.id };'
        data = run_cmd("query", "--typeql", typeql)
        assert data["count"] > 0


# ---------------------------------------------------------------------------
# C. Semantic Search (requires Qdrant + VOYAGE_API_KEY)
# ---------------------------------------------------------------------------

class TestSemanticSearch:
    """Tests for the search command (Qdrant semantic search)."""

    @requires_typedb
    @requires_qdrant
    @requires_voyage
    def test_search_basic(self):
        """search --query returns results with expected fields."""
        data = run_cmd("search", "--query", "machine learning", "--limit", "5")
        assert data["count"] >= 0
        if data["count"] > 0:
            result = data["results"][0]
            assert "collection" in result
            assert "entity_type" in result
            assert "skill" in result
            assert "score" in result
            assert "payload" in result

    @requires_typedb
    @requires_qdrant
    @requires_voyage
    def test_search_with_limit(self):
        """search --limit caps the number of results."""
        data = run_cmd("search", "--query", "gene therapy", "--limit", "2")
        assert data["count"] <= 2

    @requires_typedb
    @requires_qdrant
    @requires_voyage
    def test_search_with_threshold(self):
        """search --threshold filters low-scoring results."""
        data = run_cmd(
            "search", "--query", "CRISPR", "--threshold", "0.5", "--limit", "10"
        )
        for result in data.get("results", []):
            assert result["score"] >= 0.5

    @requires_typedb
    @requires_qdrant
    @requires_voyage
    def test_search_specific_collection(self):
        """search --collection restricts to a single Qdrant collection."""
        # First, get available collections from describe-schema
        schema = run_cmd("describe-schema")
        collections = list(schema.get("embedding_index", {}).keys())
        if not collections:
            pytest.skip("No embedding collections in registry")
        coll = collections[0]
        data = run_cmd(
            "search", "--query", "test query", "--collection", coll, "--limit", "3"
        )
        for result in data.get("results", []):
            assert result["collection"] == coll

    @requires_typedb
    @requires_qdrant
    @requires_voyage
    def test_search_nonexistent_collection(self):
        """search --collection with unknown name returns error."""
        data = run_cmd(
            "search", "--query", "test", "--collection", "nonexistent_coll_xyz",
            expect_success=False,
        )
        assert data["success"] is False


# ---------------------------------------------------------------------------
# D. Entity Alias (merge / unmerge)
# ---------------------------------------------------------------------------

class TestEntityAlias:
    """Tests for merge-entities, unmerge-entities, list-aliases.

    Creates temporary test entities, merges them, verifies, unmerges, cleans up.
    """

    @pytest.fixture(autouse=True)
    def _setup_test_entities(self):
        """Create two temporary alh-domain-thing entities for alias testing."""
        self.id_a = f"test-alias-a-{uuid.uuid4().hex[:8]}"
        self.id_b = f"test-alias-b-{uuid.uuid4().hex[:8]}"

        # Insert two test entities via query --mode write
        for eid, name in [(self.id_a, "Alias Test Entity A"), (self.id_b, "Alias Test Entity B")]:
            run_cmd(
                "query", "--mode", "write",
                "--typeql", (
                    f'insert $x isa alh-domain-thing, '
                    f'has id "{eid}", has name "{name}";'
                ),
            )

        yield

        # Cleanup: delete test entities
        for eid in [self.id_a, self.id_b]:
            try:
                run_cmd(
                    "query", "--mode", "write",
                    "--typeql", (
                        f'match $x isa alh-domain-thing, has id "{eid}"; delete $x;'
                    ),
                    expect_success=False,  # may fail if already cleaned
                )
            except Exception:
                pass

    @requires_typedb
    def test_merge_entities(self):
        """merge-entities creates an entity-alias relation."""
        data = run_cmd(
            "merge-entities",
            "--canonical", self.id_a,
            "--alias", self.id_b,
            "--description", "test merge",
        )
        assert data["canonical"] == self.id_a
        assert data["alias"] == self.id_b

    @requires_typedb
    def test_list_aliases_for_entity(self):
        """list-aliases --id shows aliases for a specific entity."""
        # First merge
        run_cmd(
            "merge-entities",
            "--canonical", self.id_a,
            "--alias", self.id_b,
        )
        data = run_cmd("list-aliases", "--id", self.id_a)
        assert len(data["aliases"]) >= 1
        other_ids = [a.get("other-id") for a in data["aliases"]]
        assert self.id_b in other_ids

    @requires_typedb
    def test_list_aliases_all(self):
        """list-aliases without --id returns all alias pairs."""
        run_cmd(
            "merge-entities",
            "--canonical", self.id_a,
            "--alias", self.id_b,
        )
        data = run_cmd("list-aliases")
        assert len(data["aliases"]) >= 1

    @requires_typedb
    def test_unmerge_entities(self):
        """unmerge-entities removes the entity-alias relation."""
        run_cmd(
            "merge-entities",
            "--canonical", self.id_a,
            "--alias", self.id_b,
        )
        data = run_cmd(
            "unmerge-entities",
            "--canonical", self.id_a,
            "--alias", self.id_b,
        )
        assert data["success"] is True

        # Verify alias is gone
        aliases = run_cmd("list-aliases", "--id", self.id_a)
        other_ids = [a.get("other-id") for a in aliases["aliases"]]
        assert self.id_b not in other_ids


# ---------------------------------------------------------------------------
# E. Episode Tracking
# ---------------------------------------------------------------------------

class TestEpisodeTracking:
    """Tests for create-episode, link-episode, show-episode, list-episodes."""

    @requires_typedb
    def test_show_existing_episode(self):
        """show-episode on a known episode returns its details."""
        data = run_cmd("show-episode", KNOWN_EPISODE_ID)
        assert data["episode"]["id"] == KNOWN_EPISODE_ID
        assert "content" in data["episode"]
        assert "entities" in data

    @requires_typedb
    def test_list_episodes(self):
        """list-episodes returns recent episodes."""
        data = run_cmd("list-episodes", "--limit", "5")
        assert len(data["episodes"]) > 0
        assert len(data["episodes"]) <= 5
        # Episodes should have expected fields
        ep = data["episodes"][0]
        assert "id" in ep
        assert "content" in ep
        assert "source-skill" in ep

    @requires_typedb
    def test_create_and_show_episode(self):
        """create-episode produces a new episode retrievable by show-episode."""
        tag = uuid.uuid4().hex[:8]
        create_data = run_cmd(
            "create-episode",
            "--skill", "test-suite",
            "--summary", f"Automated test episode {tag}",
        )
        ep_id = create_data["id"]
        assert ep_id.startswith("ep-")

        # Verify via show-episode
        show_data = run_cmd("show-episode", ep_id)
        assert show_data["episode"]["id"] == ep_id
        assert f"Automated test episode {tag}" in show_data["episode"]["content"]

        # Cleanup
        run_cmd(
            "query", "--mode", "write",
            "--typeql", f'match $e isa alh-episode, has id "{ep_id}"; delete $e;',
            expect_success=False,
        )

    @requires_typedb
    def test_link_episode_to_entity(self):
        """link-episode attaches entities to an episode with operation metadata."""
        tag = uuid.uuid4().hex[:8]

        # Create a temporary episode
        ep_data = run_cmd(
            "create-episode",
            "--skill", "test-suite",
            "--summary", f"Link test episode {tag}",
        )
        ep_id = ep_data["id"]

        # Link the known operator to this episode
        link_data = run_cmd(
            "link-episode",
            "--episode", ep_id,
            "--entities", OPERATOR_ID,
            "--operation-type", "queried",
            "--rationale", "automated test linkage",
        )
        assert link_data["episode"] == ep_id
        assert link_data["links"][0]["entity"] == OPERATOR_ID
        assert link_data["links"][0]["success"] is True

        # Verify via show-episode
        show_data = run_cmd("show-episode", ep_id)
        entity_ids = [e["id"] for e in show_data["entities"]]
        assert OPERATOR_ID in entity_ids

        # Cleanup: delete alh-episode-mention first, then episode
        run_cmd(
            "query", "--mode", "write",
            "--typeql", (
                f'match $ep isa alh-episode, has id "{ep_id}"; '
                f'$r (session: $ep, subject: $e) isa alh-episode-mention; '
                f'delete $r;'
            ),
            expect_success=False,
        )
        run_cmd(
            "query", "--mode", "write",
            "--typeql", f'match $e isa alh-episode, has id "{ep_id}"; delete $e;',
            expect_success=False,
        )


# ---------------------------------------------------------------------------
# F. Integration Pipeline
# ---------------------------------------------------------------------------

class TestIntegrationPipeline:
    """End-to-end workflows combining multiple commands."""

    @requires_typedb
    def test_get_operator_context(self):
        """get-context for the known operator returns structured context."""
        data = run_cmd("get-context", "--person", OPERATOR_ID)
        ctx = data["context"]
        assert ctx["id"] == OPERATOR_ID
        assert "name" in ctx
        assert "projects" in data
        assert "tools" in data

    @requires_typedb
    def test_consolidate_recall_invalidate_pipeline(self):
        """Full memory claim lifecycle: consolidate -> recall -> invalidate."""
        tag = uuid.uuid4().hex[:8]

        # 1. Consolidate a memory claim about the operator
        consolidate_data = run_cmd(
            "consolidate",
            "--content", f"Test memory claim {tag}",
            "--subject", OPERATOR_ID,
            "--fact-type", "knowledge",
            "--confidence", "0.75",
        )
        claim_id = consolidate_data["id"]
        assert claim_id.startswith("mcn-")

        # 2. Recall claims about the operator
        recall_data = run_cmd("recall", "--subject", OPERATOR_ID)
        claim_ids = [c["id"] for c in recall_data["claims"]]
        assert claim_id in claim_ids

        # 3. Invalidate the claim
        invalidate_data = run_cmd("invalidate", claim_id)
        assert invalidate_data["id"] == claim_id
        assert "invalidated_at" in invalidate_data

        # 4. Cleanup: delete aboutness relation, then the note
        run_cmd(
            "query", "--mode", "write",
            "--typeql", (
                f'match $n isa alh-note, has id "{claim_id}"; '
                f'$r (note: $n, subject: $e) isa alh-aboutness; '
                f'delete $r;'
            ),
            expect_success=False,
        )
        run_cmd(
            "query", "--mode", "write",
            "--typeql", (
                f'match $n isa nbmem-memory-claim-note, has id "{claim_id}"; delete $n;'
            ),
            expect_success=False,
        )
