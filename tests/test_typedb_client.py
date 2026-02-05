"""
Tests for TypeDB client.

These tests require a running TypeDB instance. To run:
    1. Start TypeDB: docker compose -f docker-compose-typedb.yml up -d
    2. Run tests: pytest tests/test_typedb_client.py -v

For CI, use pytest markers to skip if TypeDB is not available.
"""

import os
import pytest
from datetime import datetime

# Skip all tests if typedb-driver is not installed
pytest.importorskip("typedb.driver")

from skillful_alhazen.mcp.typedb_client import TypeDBClient


# Check if TypeDB is available
def typedb_available():
    """Check if TypeDB server is running."""
    try:
        client = TypeDBClient()
        client.connect()
        client.disconnect()
        return True
    except Exception:
        return False


# Skip marker for tests requiring TypeDB
requires_typedb = pytest.mark.skipif(
    not typedb_available(),
    reason="TypeDB server not available"
)


@pytest.fixture
def client():
    """Create a TypeDB client connected to test database."""
    c = TypeDBClient(database="alhazen_test")
    c.connect()

    # Create database and load schema if needed
    if not c.database_exists():
        c.create_database()
        schema_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "local_resources",
            "typedb",
            "alhazen_notebook.tql"
        )
        if os.path.exists(schema_path):
            c.load_schema(schema_path)

    yield c
    c.disconnect()


class TestTypeDBClient:
    """Test suite for TypeDB client operations."""

    @requires_typedb
    def test_connection(self):
        """Test basic connection to TypeDB."""
        client = TypeDBClient()
        client.connect()
        assert client._driver is not None
        client.disconnect()
        assert client._driver is None

    @requires_typedb
    def test_context_manager(self):
        """Test using client as context manager."""
        with TypeDBClient() as client:
            assert client._driver is not None
        # After exit, driver should be closed
        assert client._driver is None

    @requires_typedb
    def test_insert_collection(self, client):
        """Test creating a collection."""
        cid = client.insert_collection(
            name="Test Collection",
            description="A test collection",
            logical_query="papers about testing"
        )
        assert cid.startswith("collection-")

        # Verify retrieval
        collection = client.get_collection(cid)
        assert collection is not None
        assert collection.get("name") == "Test Collection"

    @requires_typedb
    def test_insert_thing(self, client):
        """Test creating a thing."""
        tid = client.insert_thing(
            name="Test Paper",
            thing_type="thing",
            abstract="This is a test abstract.",
            source_uri="https://example.com/paper"
        )
        assert tid.startswith("thing-")

        # Verify retrieval
        thing = client.get_thing(tid)
        assert thing is not None
        assert thing.get("name") == "Test Paper"

    @requires_typedb
    def test_insert_thing_with_collection(self, client):
        """Test creating a thing and adding to collection."""
        cid = client.insert_collection(name="Papers Collection")
        tid = client.insert_thing(
            name="Paper in Collection",
            collection_id=cid
        )

        # Verify membership
        members = client.get_collection_members(cid)
        assert len(members) > 0
        member_ids = [m.get("id") for m in members]
        assert tid in member_ids

    @requires_typedb
    def test_insert_artifact(self, client):
        """Test creating an artifact for a thing."""
        tid = client.insert_thing(name="Paper with Artifact")
        aid = client.insert_artifact(
            thing_id=tid,
            content="Full text content here...",
            format="text/plain",
            source_uri="https://example.com/paper.txt"
        )
        assert aid.startswith("artifact-")

        # Verify artifact is linked to thing
        artifacts = client.get_thing_artifacts(tid)
        assert len(artifacts) > 0
        artifact_ids = [a.get("id") for a in artifacts]
        assert aid in artifact_ids

    @requires_typedb
    def test_insert_fragment(self, client):
        """Test creating a fragment from an artifact."""
        tid = client.insert_thing(name="Paper with Fragment")
        aid = client.insert_artifact(
            thing_id=tid,
            content="Introduction. Methods. Results. Discussion."
        )
        fid = client.insert_fragment(
            artifact_id=aid,
            content="Methods section content",
            offset=13,
            length=8
        )
        assert fid.startswith("fragment-")

    @requires_typedb
    def test_insert_note(self, client):
        """Test creating a note about a thing."""
        tid = client.insert_thing(name="Paper with Notes")
        nid = client.insert_note(
            subject_ids=[tid],
            content="This paper demonstrates a novel approach.",
            note_type="observation",
            confidence=0.85,
            tags=["important", "methodology"]
        )
        assert nid.startswith("note-")

        # Verify note retrieval
        notes = client.query_notes_about(tid)
        assert len(notes) > 0
        note_ids = [n.get("id") for n in notes]
        assert nid in note_ids

    @requires_typedb
    def test_note_about_note(self, client):
        """Test creating a note about another note (meta-commentary)."""
        tid = client.insert_thing(name="Original Paper")
        note1_id = client.insert_note(
            subject_ids=[tid],
            content="First observation about the paper"
        )

        # Create a note about the first note
        note2_id = client.insert_note(
            subject_ids=[note1_id],
            content="This observation seems particularly important",
            note_type="meta-commentary"
        )

        # Verify the chain
        notes_about_note = client.query_notes_about(note1_id)
        assert len(notes_about_note) > 0
        note_ids = [n.get("id") for n in notes_about_note]
        assert note2_id in note_ids

    @requires_typedb
    def test_tagging(self, client):
        """Test tagging entities."""
        tid = client.insert_thing(name="Tagged Paper")
        client.tag_entity(tid, "machine-learning")
        client.tag_entity(tid, "biology")

        # Search by tag
        results = client.search_by_tag("machine-learning")
        assert len(results) > 0
        result_ids = [r.get("id") for r in results]
        assert tid in result_ids

    @requires_typedb
    def test_insert_agent(self, client):
        """Test creating an agent."""
        aid = client.insert_agent(
            name="Claude",
            agent_type="llm",
            model_name="claude-3-opus"
        )
        assert aid.startswith("agent-")

    @requires_typedb
    def test_provenance_recording(self, client):
        """Test recording provenance for derived content."""
        # Create source entities
        paper_id = client.insert_thing(name="Source Paper")

        # Create an agent
        agent_id = client.insert_agent(
            name="Extraction Agent",
            agent_type="llm"
        )

        # Create derived note
        note_id = client.insert_note(
            subject_ids=[paper_id],
            content="Extracted key findings",
            agent_id=agent_id
        )

        # Record provenance
        client.record_provenance(
            produced_entity_id=note_id,
            source_entity_ids=[paper_id],
            agent_id=agent_id,
            operation_type="extraction",
            operation_parameters={"method": "structured_extraction"}
        )

        # Verify provenance
        provenance = client.traverse_provenance(note_id)
        assert len(provenance) > 0


class TestEscaping:
    """Test string escaping for special characters."""

    @requires_typedb
    def test_escape_quotes(self, client):
        """Test that quotes in content are properly escaped."""
        tid = client.insert_thing(
            name='Paper with "quotes" in title'
        )
        thing = client.get_thing(tid)
        assert thing is not None
        assert '"quotes"' in thing.get("name", "")

    @requires_typedb
    def test_escape_newlines(self, client):
        """Test that newlines in content are properly escaped."""
        tid = client.insert_thing(
            name="Paper Title",
            abstract="Line 1\nLine 2\nLine 3"
        )
        thing = client.get_thing(tid)
        assert thing is not None

    @requires_typedb
    def test_escape_backslashes(self, client):
        """Test that backslashes are properly escaped."""
        tid = client.insert_thing(
            name="Paper with path: C:\\Users\\test"
        )
        thing = client.get_thing(tid)
        assert thing is not None
