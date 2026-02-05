"""
TypeDB MCP Server for Alhazen Notebook Model.

Provides MCP (Model Context Protocol) tools for Claude and other LLM agents
to interact with the TypeDB knowledge graph.

Usage:
    python -m skillful_alhazen.mcp.typedb_server

Environment Variables:
    TYPEDB_HOST: TypeDB server hostname (default: localhost)
    TYPEDB_PORT: TypeDB server port (default: 1729)
    TYPEDB_DATABASE: Database name (default: alhazen)
"""

import json
import os
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .typedb_client import TypeDBClient


# Configuration from environment
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen")

# Initialize MCP server
mcp = FastMCP("alhazen-typedb")


def get_client() -> TypeDBClient:
    """Get a configured TypeDB client."""
    return TypeDBClient(
        host=TYPEDB_HOST,
        port=TYPEDB_PORT,
        database=TYPEDB_DATABASE
    )


# -----------------------------------------------------------------------------
# Tool Implementations
# -----------------------------------------------------------------------------

@mcp.tool()
def insert_collection(
    name: str,
    description: Optional[str] = None,
    logical_query: Optional[str] = None
) -> str:
    """
    Create a new collection to organize research items.
    Collections can group papers, datasets, or other items together for analysis.

    Args:
        name: Human-readable name for the collection
        description: Description of what this collection contains
        logical_query: Optional query defining membership (e.g., 'papers about CRISPR from 2020-2024')

    Returns:
        JSON with collection_id and success status
    """
    try:
        with get_client() as client:
            collection_id = client.insert_collection(
                name=name,
                description=description,
                logical_query=logical_query
            )
            return json.dumps({
                "success": True,
                "collection_id": collection_id,
                "message": f"Created collection '{name}'"
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def insert_thing(
    name: str,
    thing_type: str = "research-item",
    collection_id: Optional[str] = None,
    abstract: Optional[str] = None,
    source_uri: Optional[str] = None
) -> str:
    """
    Add a new research item (paper, dataset, etc.) to the knowledge graph.
    Use this when you encounter a new paper or resource worth remembering.

    Args:
        name: Title or name of the item
        thing_type: Type of thing: research-item, scilit-paper, scilit-dataset, scilit-preprint
        collection_id: Optional collection ID to add this to
        abstract: Abstract or summary text
        source_uri: URL or URI where this was found

    Returns:
        JSON with thing_id and success status
    """
    try:
        with get_client() as client:
            thing_id = client.insert_thing(
                name=name,
                thing_type=thing_type,
                collection_id=collection_id,
                abstract=abstract,
                source_uri=source_uri
            )
            return json.dumps({
                "success": True,
                "thing_id": thing_id,
                "message": f"Created thing '{name}'"
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def insert_artifact(
    thing_id: str,
    content: Optional[str] = None,
    format: Optional[str] = None,
    source_uri: Optional[str] = None,
    artifact_type: str = "artifact"
) -> str:
    """
    Add a specific representation (PDF, XML, citation record) of a Thing.

    Args:
        thing_id: ID of the Thing this artifact represents
        content: The content/text of the artifact
        format: MIME type or format (e.g., application/pdf, text/xml)
        source_uri: URL where the artifact was obtained
        artifact_type: Type: artifact, scilit-pdf-fulltext, scilit-jats-fulltext, scilit-citation-record

    Returns:
        JSON with artifact_id and success status
    """
    try:
        with get_client() as client:
            artifact_id = client.insert_artifact(
                thing_id=thing_id,
                content=content,
                format=format,
                source_uri=source_uri,
                artifact_type=artifact_type
            )
            return json.dumps({
                "success": True,
                "artifact_id": artifact_id,
                "message": "Created artifact"
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def insert_fragment(
    artifact_id: str,
    content: str,
    offset: Optional[int] = None,
    length: Optional[int] = None,
    section_type: Optional[str] = None,
    fragment_type: str = "fragment"
) -> str:
    """
    Extract and store a fragment (section, paragraph, figure) from an artifact.

    Args:
        artifact_id: ID of the artifact this fragment comes from
        content: The content of the fragment
        offset: Start position in the parent artifact
        length: Length of the fragment
        section_type: Section type: abstract, introduction, methods, results, discussion
        fragment_type: Type: fragment, scilit-section, scilit-paragraph, scilit-figure

    Returns:
        JSON with fragment_id and success status
    """
    try:
        with get_client() as client:
            fragment_id = client.insert_fragment(
                artifact_id=artifact_id,
                content=content,
                offset=offset,
                length=length,
                section_type=section_type,
                fragment_type=fragment_type
            )
            return json.dumps({
                "success": True,
                "fragment_id": fragment_id,
                "message": "Created fragment"
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def insert_note(
    subject_ids: list[str],
    content: str,
    note_type: Optional[str] = None,
    confidence: Optional[float] = None,
    tags: Optional[list[str]] = None,
    note_class: str = "note"
) -> str:
    """
    Store a note about one or more entities.
    Use this to remember observations, summaries, extractions, or any information you want to recall later.
    Notes can be about Things, Artifacts, Fragments, or even other Notes.

    Args:
        subject_ids: IDs of entities this note is about
        content: The note content
        note_type: Type of note: observation, extraction, classification, summary, synthesis, critique
        confidence: Confidence score from 0.0 to 1.0
        tags: Tags to apply to this note
        note_class: Note class: note, scilit-extraction-note, scilit-summary-note, scilit-synthesis-note

    Returns:
        JSON with note_id and success status
    """
    try:
        with get_client() as client:
            note_id = client.insert_note(
                subject_ids=subject_ids,
                content=content,
                note_type=note_type,
                confidence=confidence,
                tags=tags,
                note_class=note_class
            )
            return json.dumps({
                "success": True,
                "note_id": note_id,
                "message": "Created note"
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def query_collection(collection_id: str) -> str:
    """
    Get information about a collection and its members.

    Args:
        collection_id: ID of the collection to query

    Returns:
        JSON with collection details and members
    """
    try:
        with get_client() as client:
            collection = client.get_collection(collection_id)
            if not collection:
                return json.dumps({"success": False, "error": "Collection not found"})

            members = client.get_collection_members(collection_id)
            return json.dumps({
                "success": True,
                "collection": collection,
                "members": members,
                "member_count": len(members)
            }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def query_thing(thing_id: str) -> str:
    """
    Get information about a Thing, including its artifacts and notes.

    Args:
        thing_id: ID of the thing to query

    Returns:
        JSON with thing details, artifacts, and notes
    """
    try:
        with get_client() as client:
            thing = client.get_thing(thing_id)
            if not thing:
                return json.dumps({"success": False, "error": "Thing not found"})

            artifacts = client.get_thing_artifacts(thing_id)
            notes = client.query_notes_about(thing_id)
            return json.dumps({
                "success": True,
                "thing": thing,
                "artifacts": artifacts,
                "notes": notes
            }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def query_notes_about(subject_id: str) -> str:
    """
    Find all notes about a given entity.
    Use this to recall what you've learned about a paper, concept, or any other entity.

    Args:
        subject_id: ID of the entity to find notes about

    Returns:
        JSON with list of notes
    """
    try:
        with get_client() as client:
            notes = client.query_notes_about(subject_id)
            return json.dumps({
                "success": True,
                "subject_id": subject_id,
                "notes": notes,
                "note_count": len(notes)
            }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def search_by_tag(tag_name: str, entity_type: Optional[str] = None) -> str:
    """
    Find all entities with a given tag.

    Args:
        tag_name: Tag to search for
        entity_type: Optional type filter: research-item, note, collection, etc.

    Returns:
        JSON with matching entities
    """
    try:
        with get_client() as client:
            entities = client.search_by_tag(
                tag_name=tag_name,
                entity_type=entity_type
            )
            return json.dumps({
                "success": True,
                "tag": tag_name,
                "entities": entities,
                "count": len(entities)
            }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def tag_entity(entity_id: str, tag_name: str) -> str:
    """
    Apply a tag to any entity for easy retrieval later.

    Args:
        entity_id: ID of the entity to tag
        tag_name: Tag to apply

    Returns:
        JSON with success status
    """
    try:
        with get_client() as client:
            client.tag_entity(
                entity_id=entity_id,
                tag_name=tag_name
            )
            return json.dumps({
                "success": True,
                "message": f"Tagged entity with '{tag_name}'"
            })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def traverse_provenance(entity_id: str) -> str:
    """
    Get the provenance chain for an entity, showing how it was created.

    Args:
        entity_id: ID of the entity

    Returns:
        JSON with provenance chain
    """
    try:
        with get_client() as client:
            provenance = client.traverse_provenance(entity_id)
            return json.dumps({
                "success": True,
                "entity_id": entity_id,
                "provenance_chain": provenance
            }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
