description: "Migrate position application status from jhunt-application-note indirection to direct jhunt-opportunity-status attribute on jhunt-position"

removals:
  - type: jhunt-application-note
    reason: "Unnecessary indirection - status should live directly on the opportunity entity"
  - attribute: jhunt-application-status
    reason: "Replaced by jhunt-opportunity-status (already exists on jhunt-opportunity)"

attribute_moves:
  - attribute: jhunt-applied-date
    from: jhunt-application-note
    to: jhunt-opportunity
    reason: "Date belongs on the opportunity, not a proxy note"
  - attribute: jhunt-response-date
    from: jhunt-application-note
    to: jhunt-opportunity
    reason: "Date belongs on the opportunity, not a proxy note"

data_transforms:
  - description: "Copy jhunt-application-status from note to jhunt-opportunity-status on linked position"
    source_pattern: "(note: $n, subject: $p) isa alh-aboutness; $n isa jhunt-application-note"
    target_attribute: jhunt-opportunity-status
