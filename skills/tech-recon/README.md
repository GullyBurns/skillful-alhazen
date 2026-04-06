# Tech-Recon Schema

Goal-driven technology investigation skill. A tech-recon investigation organizes systems, artifacts, notes, and analyses into a structured knowledge graph.

## Schema UML

```mermaid
classDiagram
    direction TB

    class `identifiable-entity` {
        <<abstract>>
        +id: string @key
        +name: string
        +description: string
        +provenance: string
        +created-at: datetime
    }

    class collection {
        <<abstract>>
    }

    class `domain-thing` {
    }

    class artifact {
        +content: string
        +cache-path: string
        +format: string
    }

    class annotation {
        +content: string
    }

    `identifiable-entity` <|-- collection
    `identifiable-entity` <|-- `domain-thing`
    `identifiable-entity` <|-- artifact
    `identifiable-entity` <|-- annotation

    class `tech-recon-investigation` {
        +goal-description: string
        +success-criteria: string
        +tech-recon-status: string
        +iteration-number: integer
    }

    class `tech-recon-system` {
        +tech-recon-url: string
        +github-url: string
        +tech-recon-language: string
        +star-count: integer
        +tech-recon-status: string
    }

    class `tech-recon-artifact` {
        +artifact-type: string
        +tech-recon-url: string
    }

    class `tech-recon-analysis` {
        +tech-recon-title: string
        +analysis-type: string
        +plot-code: string
        +tql-query: string
        +pipeline-script: string
        +pipeline-config: string
    }

    class `tech-recon-note` {
        +topic: string
        +tech-recon-tag: string
        +iteration-number: integer
    }

    collection <|-- `tech-recon-investigation`
    `domain-thing` <|-- `tech-recon-system`
    artifact <|-- `tech-recon-artifact`
    artifact <|-- `tech-recon-analysis`
    annotation <|-- `tech-recon-note`

    class `investigated-in` {
        <<relation>>
    }
    class `sourced-from` {
        <<relation>>
    }
    class `analysis-of` {
        <<relation>>
    }
    class aboutness {
        <<relation>>
    }

    `tech-recon-system` --> `investigated-in` : system
    `tech-recon-investigation` --> `investigated-in` : investigation

    `tech-recon-artifact` --> `sourced-from` : artifact
    `tech-recon-system` --> `sourced-from` : source
    `tech-recon-investigation` --> `sourced-from` : source

    `tech-recon-analysis` --> `analysis-of` : analysis
    `tech-recon-investigation` --> `analysis-of` : investigation

    `tech-recon-note` --> aboutness : note
    `identifiable-entity` --> aboutness : subject
```

> `annotation` above represents the TypeDB `note` base type (renamed to avoid a Mermaid parser conflict — `note` is a reserved keyword and cannot appear anywhere in a class identifier).
