#!/usr/bin/env python3
"""Export jobhunt-contact and jobhunt-company data before person model migration."""
import json
import sys
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType

TYPEDB_HOST = "localhost"
TYPEDB_PORT = 1729
TYPEDB_DATABASE = "alhazen_notebook"

def export_data():
    driver = TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials("admin", "password"),
        DriverOptions(is_tls_enabled=False),
    )

    data = {"contacts": [], "companies": [], "works_at": []}

    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        # Export contacts
        contacts = list(tx.query('''
            match $c isa jobhunt-contact;
            fetch {
                "id": $c.id,
                "name": $c.name,
                "contact_role": $c.contact-role,
                "contact_email": $c.contact-email,
                "linkedin_url": $c.linkedin-url
            };
        ''').resolve())
        data["contacts"] = contacts
        print(f"Exported {len(contacts)} contacts", file=sys.stderr)

        # Export companies
        companies = list(tx.query('''
            match $c isa jobhunt-company;
            fetch {
                "id": $c.id,
                "name": $c.name,
                "company_url": $c.company-url,
                "linkedin_url": $c.linkedin-url,
                "location": $c.location
            };
        ''').resolve())
        data["companies"] = companies
        print(f"Exported {len(companies)} companies", file=sys.stderr)

        # Export works-at relations
        works_at = list(tx.query('''
            match
                (employee: $e, employer: $c) isa works-at;
                $e has id $eid;
                $c has id $cid;
            fetch { "employee_id": $eid, "company_id": $cid };
        ''').resolve())
        data["works_at"] = works_at
        print(f"Exported {len(works_at)} works-at relations", file=sys.stderr)

    driver.close()
    json.dump(data, sys.stdout, indent=2)

if __name__ == "__main__":
    export_data()
