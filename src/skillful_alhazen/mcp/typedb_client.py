"""
TypeDB Client wrapper for Alhazen Notebook Model operations.

Provides high-level operations for inserting and querying entities
in the Alhazen knowledge graph stored in TypeDB.
"""

import json
import uuid
from datetime import datetime
from typing import Any

from typedb.driver import SessionType, TransactionType, TypeDB


class TypeDBClient:
    """
    Client for TypeDB operations aligned with Alhazen's Notebook Model.

    Provides CRUD operations for:
    - Collections (groupings of Things)
    - Things (research objects like papers)
    - Artifacts (representations like PDFs, JATS XML)
    - Fragments (sections, paragraphs, figures)
    - Notes (agent-generated annotations)
    """

    def __init__(self, host: str = "localhost", port: int = 1729, database: str = "alhazen"):
        """
        Initialize TypeDB client.

        Args:
            host: TypeDB server hostname
            port: TypeDB server port
            database: Database name to use
        """
        self.address = f"{host}:{port}"
        self.database = database
        self._driver = None

    def connect(self) -> None:
        """Establish connection to TypeDB server."""
        self._driver = TypeDB.core_driver(self.address)

    def disconnect(self) -> None:
        """Close connection to TypeDB server."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID with the given prefix."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format for TypeDB datetime."""
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    # -------------------------------------------------------------------------
    # Database Management
    # -------------------------------------------------------------------------

    def create_database(self) -> bool:
        """Create the database if it doesn't exist."""
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        if not self._driver.databases.contains(self.database):
            self._driver.databases.create(self.database)
            return True
        return False

    def load_schema(self, schema_path: str) -> None:
        """
        Load a TypeQL schema file into the database.

        Args:
            schema_path: Path to the .tql schema file
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        with open(schema_path) as f:
            schema = f.read()

        with self._driver.session(self.database, SessionType.SCHEMA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.define(schema)
                tx.commit()

    def database_exists(self) -> bool:
        """Check if the database exists."""
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")
        return self._driver.databases.contains(self.database)

    # -------------------------------------------------------------------------
    # Collection Operations
    # -------------------------------------------------------------------------

    def insert_collection(
        self,
        name: str,
        description: str | None = None,
        logical_query: str | None = None,
        is_extensional: bool = True,
        collection_id: str | None = None,
    ) -> str:
        """
        Insert a new Collection into the knowledge graph.

        Args:
            name: Human-readable name for the collection
            description: Optional description of the collection
            logical_query: Optional query defining membership (for intensional collections)
            is_extensional: Whether membership is enumerated (True) or query-defined (False)
            collection_id: Optional specific ID; generated if not provided

        Returns:
            The ID of the created collection
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        cid = collection_id or self._generate_id("collection")
        timestamp = self._get_timestamp()

        query = f"""
            insert $c isa collection,
                has id "{cid}",
                has name "{name}",
                has created-at {timestamp},
                has is-extensional {str(is_extensional).lower()};
        """

        if description:
            query = query.rstrip(";") + f', has description "{description}";'
        if logical_query:
            query = query.rstrip(";") + f', has logical-query "{logical_query}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        return cid

    def get_collection(self, collection_id: str) -> dict[str, Any] | None:
        """
        Retrieve a Collection by ID.

        Args:
            collection_id: The ID of the collection to retrieve

        Returns:
            Dictionary with collection data, or None if not found
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match $c isa collection, has id "{collection_id}";
            fetch $c: id, name, description, logical-query, is-extensional, created-at;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                if results:
                    return self._parse_fetch_result(results[0])
        return None

    def get_collection_members(self, collection_id: str) -> list[dict[str, Any]]:
        """
        Get all members (Things) of a Collection.

        Args:
            collection_id: The ID of the collection

        Returns:
            List of member Thing dictionaries
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match
                $c isa collection, has id "{collection_id}";
                (collection: $c, member: $m) isa collection-membership;
            fetch $m: id, name, description, abstract-text;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                return [self._parse_fetch_result(r) for r in results]

    # -------------------------------------------------------------------------
    # Thing Operations
    # -------------------------------------------------------------------------

    def insert_thing(
        self,
        name: str,
        thing_type: str = "research-item",
        collection_id: str | None = None,
        abstract: str | None = None,
        description: str | None = None,
        publication_date: str | None = None,
        source_uri: str | None = None,
        thing_id: str | None = None,
    ) -> str:
        """
        Insert a new Thing into the knowledge graph.

        Args:
            name: Human-readable name/title for the thing
            thing_type: The specific type (research-item, scilit-paper, etc.)
            collection_id: Optional collection to add this thing to
            abstract: Optional abstract text
            description: Optional description
            publication_date: Optional publication date (ISO format)
            source_uri: Optional source URI
            thing_id: Optional specific ID; generated if not provided

        Returns:
            The ID of the created thing
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        tid = thing_id or self._generate_id("thing")
        timestamp = self._get_timestamp()

        query = f"""
            insert $t isa {thing_type},
                has id "{tid}",
                has name "{self._escape_string(name)}",
                has created-at {timestamp};
        """

        if abstract:
            query = query.rstrip(";") + f', has abstract-text "{self._escape_string(abstract)}";'
        if description:
            query = query.rstrip(";") + f', has description "{self._escape_string(description)}";'
        if publication_date:
            query = query.rstrip(";") + f", has publication-date {publication_date};"
        if source_uri:
            query = query.rstrip(";") + f', has source-uri "{source_uri}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        # Add to collection if specified
        if collection_id:
            self.add_to_collection(collection_id, tid)

        return tid

    def get_thing(self, thing_id: str) -> dict[str, Any] | None:
        """
        Retrieve a Thing by ID.

        Args:
            thing_id: The ID of the thing to retrieve

        Returns:
            Dictionary with thing data, or None if not found
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match $t isa research-item, has id "{thing_id}";
            fetch $t: id, name, description, abstract-text, publication-date, source-uri;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                if results:
                    return self._parse_fetch_result(results[0])
        return None

    def add_to_collection(self, collection_id: str, member_id: str) -> None:
        """
        Add a Thing to a Collection.

        Args:
            collection_id: The ID of the collection
            member_id: The ID of the thing to add
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        timestamp = self._get_timestamp()

        query = f"""
            match
                $c isa collection, has id "{collection_id}";
                $m isa information-content-entity, has id "{member_id}";
            insert
                (collection: $c, member: $m) isa collection-membership,
                    has created-at {timestamp};
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    # -------------------------------------------------------------------------
    # Artifact Operations
    # -------------------------------------------------------------------------

    def insert_artifact(
        self,
        thing_id: str,
        content: str | None = None,
        format: str | None = None,
        source_uri: str | None = None,
        artifact_type: str = "artifact",
        artifact_id: str | None = None,
    ) -> str:
        """
        Insert a new Artifact representing a Thing.

        Args:
            thing_id: The ID of the thing this artifact represents
            content: Optional content of the artifact
            format: MIME type or format identifier
            source_uri: Optional source URI
            artifact_type: The specific type (artifact, scilit-pdf-fulltext, etc.)
            artifact_id: Optional specific ID; generated if not provided

        Returns:
            The ID of the created artifact
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        aid = artifact_id or self._generate_id("artifact")
        timestamp = self._get_timestamp()

        # First insert the artifact
        query = f"""
            insert $a isa {artifact_type},
                has id "{aid}",
                has created-at {timestamp};
        """

        if content:
            query = query.rstrip(";") + f', has content "{self._escape_string(content)}";'
        if format:
            query = query.rstrip(";") + f', has format "{format}";'
        if source_uri:
            query = query.rstrip(";") + f', has source-uri "{source_uri}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        # Create representation relation
        rel_query = f"""
            match
                $t isa research-item, has id "{thing_id}";
                $a isa artifact, has id "{aid}";
            insert
                (artifact: $a, referent: $t) isa representation;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(rel_query)
                tx.commit()

        return aid

    def get_thing_artifacts(self, thing_id: str) -> list[dict[str, Any]]:
        """
        Get all Artifacts for a Thing.

        Args:
            thing_id: The ID of the thing

        Returns:
            List of artifact dictionaries
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match
                $t isa research-item, has id "{thing_id}";
                (artifact: $a, referent: $t) isa representation;
            fetch $a: id, format, source-uri, created-at;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                return [self._parse_fetch_result(r) for r in results]

    # -------------------------------------------------------------------------
    # Fragment Operations
    # -------------------------------------------------------------------------

    def insert_fragment(
        self,
        artifact_id: str,
        content: str,
        offset: int | None = None,
        length: int | None = None,
        section_type: str | None = None,
        fragment_type: str = "fragment",
        fragment_id: str | None = None,
    ) -> str:
        """
        Insert a new Fragment of an Artifact.

        Args:
            artifact_id: The ID of the artifact this fragment comes from
            content: The content of the fragment
            offset: Optional start offset in the parent artifact
            length: Optional length of the fragment
            section_type: Optional section type (for scilit-section)
            fragment_type: The specific type (fragment, scilit-section, etc.)
            fragment_id: Optional specific ID; generated if not provided

        Returns:
            The ID of the created fragment
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        fid = fragment_id or self._generate_id("fragment")
        timestamp = self._get_timestamp()

        query = f"""
            insert $f isa {fragment_type},
                has id "{fid}",
                has content "{self._escape_string(content)}",
                has created-at {timestamp};
        """

        if offset is not None:
            query = query.rstrip(";") + f", has offset {offset};"
        if length is not None:
            query = query.rstrip(";") + f", has length {length};"
        if section_type and fragment_type == "scilit-section":
            query = query.rstrip(";") + f', has section-type "{section_type}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        # Create fragmentation relation
        rel_query = f"""
            match
                $a isa artifact, has id "{artifact_id}";
                $f isa fragment, has id "{fid}";
            insert
                (whole: $a, part: $f) isa fragmentation;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(rel_query)
                tx.commit()

        return fid

    # -------------------------------------------------------------------------
    # Note Operations
    # -------------------------------------------------------------------------

    def insert_note(
        self,
        subject_ids: list[str],
        content: str,
        note_type: str | None = None,
        confidence: float | None = None,
        tags: list[str] | None = None,
        agent_id: str | None = None,
        note_class: str = "note",
        note_id: str | None = None,
    ) -> str:
        """
        Insert a new Note about one or more entities.

        Args:
            subject_ids: List of entity IDs this note is about
            content: The content of the note
            note_type: Optional type of note (extraction, classification, summary, etc.)
            confidence: Optional confidence score (0.0-1.0)
            tags: Optional list of tag names to apply
            agent_id: Optional ID of the agent creating this note
            note_class: The specific note type (note, scilit-extraction-note, etc.)
            note_id: Optional specific ID; generated if not provided

        Returns:
            The ID of the created note
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        nid = note_id or self._generate_id("note")
        timestamp = self._get_timestamp()

        # Insert the note
        query = f"""
            insert $n isa {note_class},
                has id "{nid}",
                has content "{self._escape_string(content)}",
                has created-at {timestamp};
        """

        if confidence is not None:
            query = query.rstrip(";") + f", has confidence {confidence};"
        if note_type:
            query = query.rstrip(";") + f', has format "{note_type}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        # Create aboutness relations for each subject
        for subject_id in subject_ids:
            rel_query = f"""
                match
                    $n isa note, has id "{nid}";
                    $s isa information-content-entity, has id "{subject_id}";
                insert
                    (note: $n, subject: $s) isa aboutness;
            """
            with self._driver.session(self.database, SessionType.DATA) as session:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(rel_query)
                    tx.commit()

        # Apply tags
        if tags:
            for tag_name in tags:
                self.tag_entity(nid, tag_name)

        # Record authorship if agent specified
        if agent_id:
            auth_query = f"""
                match
                    $n isa note, has id "{nid}";
                    $a isa agent, has id "{agent_id}";
                insert
                    (author: $a, work: $n) isa authorship,
                        has created-at {timestamp};
            """
            with self._driver.session(self.database, SessionType.DATA) as session:
                with session.transaction(TransactionType.WRITE) as tx:
                    tx.query.insert(auth_query)
                    tx.commit()

        return nid

    def query_notes_about(self, subject_id: str) -> list[dict[str, Any]]:
        """
        Get all Notes about a given entity.

        Args:
            subject_id: The ID of the entity to find notes about

        Returns:
            List of note dictionaries
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match
                $s isa information-content-entity, has id "{subject_id}";
                (note: $n, subject: $s) isa aboutness;
            fetch $n: id, content, confidence, format, created-at;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                return [self._parse_fetch_result(r) for r in results]

    # -------------------------------------------------------------------------
    # Tagging Operations
    # -------------------------------------------------------------------------

    def create_tag(self, name: str, description: str | None = None) -> str:
        """
        Create a new Tag.

        Args:
            name: The tag name
            description: Optional description

        Returns:
            The ID of the created tag
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        tag_id = self._generate_id("tag")

        query = f"""
            insert $t isa tag,
                has id "{tag_id}",
                has name "{name}";
        """

        if description:
            query = query.rstrip(";") + f', has description "{description}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        return tag_id

    def tag_entity(self, entity_id: str, tag_name: str) -> None:
        """
        Apply a tag to an entity. Creates the tag if it doesn't exist.

        Args:
            entity_id: The ID of the entity to tag
            tag_name: The name of the tag
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        timestamp = self._get_timestamp()

        # Check if tag exists
        check_query = f"""
            match $t isa tag, has name "{tag_name}";
            fetch $t: id;
        """

        tag_id = None
        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(check_query))
                if results:
                    tag_id = self._parse_fetch_result(results[0]).get("id")

        # Create tag if needed
        if not tag_id:
            tag_id = self.create_tag(tag_name)

        # Create tagging relation
        rel_query = f"""
            match
                $e isa information-content-entity, has id "{entity_id}";
                $t isa tag, has name "{tag_name}";
            insert
                (tagged-entity: $e, tag: $t) isa tagging,
                    has created-at {timestamp};
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(rel_query)
                tx.commit()

    def search_by_tag(self, tag_name: str, entity_type: str | None = None) -> list[dict[str, Any]]:
        """
        Find all entities with a given tag.

        Args:
            tag_name: The tag to search for
            entity_type: Optional entity type filter

        Returns:
            List of matching entity dictionaries
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        type_constraint = entity_type or "information-content-entity"

        query = f"""
            match
                $t isa tag, has name "{tag_name}";
                (tagged-entity: $e, tag: $t) isa tagging;
                $e isa {type_constraint};
            fetch $e: id, name, description;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                return [self._parse_fetch_result(r) for r in results]

    # -------------------------------------------------------------------------
    # Agent Operations
    # -------------------------------------------------------------------------

    def insert_agent(
        self,
        name: str,
        agent_type: str = "llm",
        model_name: str | None = None,
        agent_id: str | None = None,
    ) -> str:
        """
        Insert a new Agent.

        Args:
            name: Name of the agent
            agent_type: Type of agent (human, llm, automated)
            model_name: Optional model name for LLM agents
            agent_id: Optional specific ID; generated if not provided

        Returns:
            The ID of the created agent
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        aid = agent_id or self._generate_id("agent")

        query = f"""
            insert $a isa agent,
                has id "{aid}",
                has name "{name}",
                has agent-type "{agent_type}";
        """

        if model_name:
            query = query.rstrip(";") + f', has model-name "{model_name}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        return aid

    # -------------------------------------------------------------------------
    # Provenance Operations
    # -------------------------------------------------------------------------

    def record_provenance(
        self,
        produced_entity_id: str,
        source_entity_ids: list[str],
        agent_id: str,
        operation_type: str,
        operation_parameters: dict | None = None,
    ) -> None:
        """
        Record provenance for an entity.

        Args:
            produced_entity_id: ID of the entity that was produced
            source_entity_ids: IDs of entities used as sources
            agent_id: ID of the agent that performed the operation
            operation_type: Type of operation (extraction, classification, etc.)
            operation_parameters: Optional parameters as a dictionary
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        timestamp = self._get_timestamp()

        # Build match clause for all entities
        match_clauses = [
            f'$produced isa information-content-entity, has id "{produced_entity_id}";',
            f'$agent isa agent, has id "{agent_id}";',
        ]

        for i, source_id in enumerate(source_entity_ids):
            match_clauses.append(
                f'$source{i} isa information-content-entity, has id "{source_id}";'
            )

        # Build insert clause
        insert_base = """
            (produced-entity: $produced, performing-agent: $agent"""

        for i in range(len(source_entity_ids)):
            insert_base += f", source-entity: $source{i}"

        insert_base += f""") isa provenance-record,
            has operation-type "{operation_type}",
            has operation-timestamp {timestamp}"""

        if operation_parameters:
            params_json = json.dumps(operation_parameters).replace('"', '\\"')
            insert_base += f', has operation-parameters "{params_json}"'

        insert_base += ";"

        query = f"""
            match
                {" ".join(match_clauses)}
            insert
                {insert_base}
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

    def traverse_provenance(self, entity_id: str) -> list[dict[str, Any]]:
        """
        Get the provenance chain for an entity.

        Args:
            entity_id: The ID of the entity

        Returns:
            List of provenance records
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match
                $e isa information-content-entity, has id "{entity_id}";
                $p (produced-entity: $e) isa provenance-record;
            fetch
                $p: operation-type, operation-timestamp, operation-parameters;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                return [self._parse_fetch_result(r) for r in results]

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _escape_string(self, s: str) -> str:
        """Escape special characters for TypeQL strings."""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _parse_fetch_result(self, result: dict) -> dict[str, Any]:
        """Parse a TypeDB fetch result into a simple dictionary."""
        parsed = {}
        for key, value in result.items():
            if isinstance(value, dict):
                # Nested entity
                for attr_name, attr_value in value.items():
                    if attr_name != "type":
                        if isinstance(attr_value, list) and len(attr_value) == 1:
                            parsed[attr_name] = attr_value[0].get("value")
                        elif isinstance(attr_value, dict):
                            parsed[attr_name] = attr_value.get("value")
            else:
                parsed[key] = value
        return parsed

    # -------------------------------------------------------------------------
    # Scientific Literature Operations (EPMC Integration)
    # -------------------------------------------------------------------------

    def insert_paper(
        self,
        title: str,
        doi: str,
        paper_type: str = "scilit-paper",
        pmid: str | None = None,
        pmcid: str | None = None,
        abstract: str | None = None,
        publication_year: int | None = None,
        journal_name: str | None = None,
        keywords: list[str] | None = None,
        collection_id: str | None = None,
        paper_id: str | None = None,
    ) -> str:
        """
        Insert a scientific paper into the knowledge graph.

        Args:
            title: Paper title
            doi: Digital Object Identifier
            paper_type: TypeDB type (scilit-paper, scilit-review, scilit-preprint)
            pmid: Optional PubMed ID
            pmcid: Optional PubMed Central ID
            abstract: Optional abstract text
            publication_year: Optional publication year
            journal_name: Optional journal name
            keywords: Optional list of keywords
            collection_id: Optional collection to add paper to
            paper_id: Optional specific ID; generated from DOI if not provided

        Returns:
            The ID of the created paper
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        # Generate ID from DOI if not provided
        pid = paper_id or f"doi-{doi.replace('/', '-').replace('.', '_')}"
        timestamp = self._get_timestamp()

        query = f"""
            insert $p isa {paper_type},
                has id "{pid}",
                has name "{self._escape_string(title)}",
                has doi "{doi}",
                has created-at {timestamp};
        """

        if pmid:
            query = query.rstrip(";") + f', has pmid "{pmid}";'
        if pmcid:
            query = query.rstrip(";") + f', has pmcid "{pmcid}";'
        if abstract:
            query = query.rstrip(";") + f', has abstract-text "{self._escape_string(abstract)}";'
        if publication_year:
            query = query.rstrip(";") + f", has publication-year {publication_year};"
        if journal_name:
            query = query.rstrip(";") + f', has journal-name "{self._escape_string(journal_name)}";'
        if keywords:
            for kw in keywords:
                query = query.rstrip(";") + f', has keyword "{self._escape_string(kw)}";'

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.WRITE) as tx:
                tx.query.insert(query)
                tx.commit()

        # Add to collection if specified
        if collection_id:
            self.add_to_collection(collection_id, pid)

        return pid

    def get_paper_by_doi(self, doi: str) -> dict[str, Any] | None:
        """
        Retrieve a paper by its DOI.

        Args:
            doi: The DOI to search for

        Returns:
            Dictionary with paper data, or None if not found
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match $p isa research-item, has doi "{doi}";
            fetch $p: id, name, doi, pmid, pmcid, abstract-text, publication-year, journal-name;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                if results:
                    return self._parse_fetch_result(results[0])
        return None

    def search_papers(
        self,
        keyword: str | None = None,
        year: int | None = None,
        journal: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search for papers in the knowledge graph.

        Args:
            keyword: Optional keyword to search for in title/abstract
            year: Optional publication year filter
            journal: Optional journal name filter
            limit: Maximum results to return

        Returns:
            List of matching paper dictionaries
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        match_clauses = ["$p isa research-item"]
        if keyword:
            match_clauses.append(f'$p has keyword "{self._escape_string(keyword)}"')
        if year:
            match_clauses.append(f"$p has publication-year {year}")
        if journal:
            match_clauses.append(f'$p has journal-name "{self._escape_string(journal)}"')

        query = f"""
            match {"; ".join(match_clauses)};
            fetch $p: id, name, doi, publication-year, journal-name;
            limit {limit};
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                return [self._parse_fetch_result(r) for r in results]

    def get_papers_in_collection(self, collection_id: str) -> list[dict[str, Any]]:
        """
        Get all papers in a collection with their metadata.

        Args:
            collection_id: The ID of the collection

        Returns:
            List of paper dictionaries
        """
        if not self._driver:
            raise RuntimeError("Not connected to TypeDB")

        query = f"""
            match
                $c isa collection, has id "{collection_id}";
                (collection: $c, member: $p) isa collection-membership;
                $p isa research-item;
            fetch $p: id, name, doi, pmid, abstract-text, publication-year, journal-name;
        """

        with self._driver.session(self.database, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                results = list(tx.query.fetch(query))
                return [self._parse_fetch_result(r) for r in results]
