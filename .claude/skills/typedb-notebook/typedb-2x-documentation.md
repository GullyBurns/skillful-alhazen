# TypeDB 2.x Documentation Reference

This document compiles comprehensive documentation for TypeDB 2.x and TypeQL, the query language for TypeDB. It serves as a reference for building knowledge graphs and working with the TypeDB database.

> **Note**: This documentation is for TypeDB 2.x. For current projects, check if TypeDB 3.x documentation is applicable.

---

## Table of Contents

1. [TypeQL Overview](#typeql-overview)
2. [Queries](#queries)
   - [Define Query](#define-query)
   - [Undefine Query](#undefine-query)
   - [Insert Query](#insert-query)
   - [Delete Query](#delete-query)
   - [Update Query](#update-query)
   - [Fetch Query](#fetch-query)
   - [Get Query](#get-query)
3. [Patterns](#patterns)
   - [Conjunction](#conjunction)
   - [Disjunction (OR)](#disjunction-or)
   - [Negation (NOT)](#negation-not)
4. [Statements](#statements)
   - [isa / isa!](#isa--isa)
   - [has](#has)
   - [sub / sub!](#sub--sub)
   - [owns](#owns)
   - [relates](#relates)
   - [plays](#plays)
   - [rule](#rule)
5. [Types and Concepts](#types-and-concepts)
   - [Type Hierarchy](#type-hierarchy)
   - [Concept Variables](#concept-variables)
6. [Values](#values)
   - [Value Types](#value-types)
   - [Comparators](#comparators)
   - [Arithmetic](#arithmetic)
   - [Built-in Functions](#built-in-functions)
7. [Query Modifiers](#query-modifiers)
   - [Sorting](#sorting)
   - [Pagination](#pagination)
   - [Aggregation](#aggregation)
   - [Grouping](#grouping)
8. [Keywords Reference](#keywords-reference)
9. [Python Driver](#python-driver)

---

## TypeQL Overview

TypeQL is the query language built specifically for TypeDB. It is designed around principles that distinguish it from traditional query languages, with dedicated support for semantic querying and type-driven data operations.

### Query Types

TypeQL supports seven distinct query categories:

| Query Type | Purpose |
|------------|---------|
| **Define** | Add types and rules to schemas |
| **Undefine** | Remove types and rules from schemas |
| **Insert** | Add data to databases |
| **Delete** | Remove data from databases |
| **Update** | Replace existing data |
| **Fetch** | Retrieve values and types as JSON |
| **Get** | Retrieve data and types as stateful objects |

### Core Components

TypeQL queries are constructed from several architectural layers:

- **Patterns**: Support conjunction, disjunction (OR), negation (NOT), and matching operations
- **Statements**: Include operators like `isa`, `has`, `sub`, `owns`, `abstract`, `relates`, and role/value assignments
- **Modifiers**: Enable sorting, pagination, aggregation, and grouping of results
- **Concepts**: Work with types, data instances, and concept variables
- **Values**: Handle value-types, comparators, arithmetic operations, and built-in functions

---

## Queries

### Query Categories

**Schema Queries (DDL)**
- **Define Query**: Establishes new types and rules within a schema structure
- **Undefine Query**: Removes existing types and rules from a schema

**Data Queries (DML)**
- **Insert Query**: Introduces new data records into a database
- **Delete Query**: Removes existing data from a database
- **Update Query**: Modifies and replaces existing data records
- **Fetch Query**: Retrieves values and types as JSONs
- **Get Query**: Gets concepts from a database as ConceptMaps or aggregated values

A TypeQL query uses from one to three clauses with fully declarative patterns to manipulate the schema or data of a database.

---

### Define Query

A Define query extends a database schema with new schema statements.

#### Syntax

```typeql
define <schema_definitions>
```

The query accepts valid schema statements including: `sub`/`sub!`, `abstract`, `owns`, `value`, `regex`, `relates`, `plays`, `rule`, and annotations (`@key`, `@unique`).

> Schema statements in a `define` clause can't use any variables or values, except for rules.

#### Key Behaviors

- **Idempotency**: Define queries can be applied multiple times without altering the initial result
- **Schema Validation**: A Define query must produce a valid schema in a database, otherwise it will be rejected
- **Response**: A successful Define query returns an empty response

#### Example: Defining Types

```typeql
define

credential sub attribute, value string;
email sub attribute, value string;
full-name sub attribute, value string;
review-date sub attribute, value datetime;

subject sub entity,
    abstract,
    owns credential,
    plays permission:subject;
user sub subject, abstract;
person sub user,
    owns email,
    owns full-name;

permission sub relation,
    owns review-date,
    relates subject;
```

#### Example: Defining Rules

```typeql
define

rule add-view-permission: when {
    $modify isa action, has name "modify_file";
    $view isa action, has name "view_file";
    $ac_modify (object: $obj, action: $modify) isa access;
    $ac_view (object: $obj, action: $view) isa access;
    (subject: $subj, access: $ac_modify) isa permission;
} then {
    (subject: $subj, access: $ac_view) isa permission;
};
```

---

### Undefine Query

An Undefine query removes type and rule definitions from a TypeDB schema.

#### Syntax

```typeql
undefine <schema_definitions>
```

Valid schema statements include: `sub`/`sub!`, `abstract`, `owns`, `value`, `regex`, `relates`, `plays`, `rule`, and annotations like `@key` and `@unique`.

#### Behavior Rules

- Types targeted for deletion must exist
- Types cannot have subtypes or data instances
- The resulting schema must remain valid
- Duplicate undefine operations cause errors

> Undefining a type also undefines all ownerships of attribute types and all roles of that type.

#### Examples

**Removing Types and Ownerships:**
```typeql
undefine
number sub attribute;
database owns name;
```

**Removing Rules:**
```typeql
undefine
rule add-view-permission;
```

---

### Insert Query

Insert queries add new data to TypeDB databases. They enable creation of entities, attributes, relations, and ownership assignments.

#### Syntax

```typeql
[match <pattern>]
insert <insert_pattern>
```

The match clause is optional. The insert pattern uses valid data-specific TypeQL statements including `isa/isa!`, `has`, role assignments, and value assignments.

#### Core Behavior

- If a match clause exists, the insert clause executes once per match result
- Without matching, insertion occurs exactly once
- Data must comply with the database schema
- Insert queries return a lazy Stream/Iterator of ConceptMap objects

#### Examples

**Basic Entity Insertion (No Matching):**
```typeql
insert $p isa person, has full-name "Bob";
```

**Insert with Matching:**
```typeql
match
$p isa person, has full-name "Bob";
insert
$p has email "bob@typedb.com";
```

**Entity with Attributes:**
```typeql
insert
$p isa person, has full-name "John Parkson";
```

**Explicit Attribute Insertion:**
```typeql
insert
$s 34 isa size-kb;
```

**Multivalued Attributes:**
```typeql
match
$p isa person, has full-name "John Parkson";
insert
$p has email "john.parkson@typedb.com",
    has email "admin@jp.com",
    has email "jp@gmail.com";
```

**Relation Insertion:**
```typeql
match
$op isa operation, has name "view_file";
insert
$f isa file, has path "new-relation.txt";
$a (object: $f, action: $op) isa access;
```

**Adding Role Players to Existing Relation:**
```typeql
match
$f isa file, has path "new-relation.txt";
$op isa operation, has name "view_file";
$a (action: $op) isa access;
insert
$a (object: $f);
```

**Multiple Role Players for One Role:**
```typeql
match
$p1 isa subject, has full-name "Pearle Goodman";
$p2 isa subject, has full-name "Masako Holley";
$o isa object, has path "zewhb.java";
insert
$obj-ownership (owner: $p1, owner: $p2, object: $o) isa object-ownership;
```

#### Best Practices

- Entities without attributes are difficult to distinguish and find later
- Orphaned attributes (unowned attributes) aren't useful for storage
- Use `@key` or `@unique` annotations for easy instance identification
- Change attribute values by deleting old ownerships and adding new ones

---

### Delete Query

A Delete query removes data from a database. You can delete a data instance, ownership of an attribute, or a role player reference of a relation.

#### Syntax

```typeql
match <pattern>
delete <delete_pattern>
```

#### Key Behaviors

- A `delete` clause is executed once per every result of a preceding `match` clause
- Matching completes before deletion begins, so deletions don't affect the matched result set
- **Idempotency**: Deleting the same concept twice will not result in any further changes
- Since version 2.22.0, queries don't fail when attempting to delete non-existent data
- Delete queries return an empty response upon completion

#### Examples

**Deleting Data Instances:**
```typeql
match
$p isa person, has email "john.parkson@gmail.com";
delete
$p isa person;
```

When an instance is deleted, all assignments of roles played and attribute ownerships are also deleted.

**Deleting Ownerships:**
```typeql
match
$p has full-name $fn;
$fn == "Bob";
delete
$p has $fn;
```

**Deleting Role Players:**
```typeql
match
$p isa person, has full-name "Pearle Goodman";
$pe (subject: $p) isa permission;
delete
$pe ($p);
```

**Using Type Inheritance:**
```typeql
match
$fn == "Bob";
delete
$fn isa attribute;
```

#### Special Considerations

- **Orphaned Attributes**: Attributes with no owners aren't automatically deleted. They can be manually removed using negation patterns.
- **Incomplete Relations**: Deleting all role players from a relation implicitly deletes the relation at commit time, since relations must have at least one role player to exist.

---

### Update Query

An Update query modifies data by combining delete and insert operations.

#### Syntax

```typeql
match <pattern>
delete <delete_pattern>
insert <insert_pattern>
```

The query execution follows this sequence: First, the `match` clause identifies target data. Then `delete` removes specified elements. Finally, `insert` adds new data using the same matched results.

#### Key Constraints

- Data that is assumed to exist in `insert` must not be deleted in the preceding `delete` clause
- Inserted data cannot violate the database schema
- Returns a lazy Stream/Iterator of ConceptMap containing inserted data

#### Examples

**Updating Ownerships:**
```typeql
match
$p isa person,
    has full-name "Masako Holley",
    has email $email;
delete
$p has $email;
insert
$p has email "m.holley@typedb.com";
```

**Updating Attributes:**
```typeql
match
$p isa person, has full-name $n;
$n contains "inappropriate word";
delete
$n isa full-name;
insert
$p has full-name "deleted";
```

**Updating Role Players:**
```typeql
match
$p isa person, has full-name "Pearle Goodman";
$a_write isa action, has name "modify_file";
$a_read isa action, has name "view_file";
$ac_write (object: $o, action: $a_write) isa access;
$ac_read (object: $o, action: $a_read) isa access;
$pe (subject: $p, access: $ac_write) isa permission;
delete
$pe (access: $ac_write);
insert
$pe (access: $ac_read);
```

---

### Fetch Query

A Fetch query retrieves values from TypeDB and returns them as JSON objects.

#### Syntax

```typeql
match <pattern>
fetch
  {  <variable> [as <label>]
   | <variable> [as <label>] : (<attribute-type> [as <label>]), ...
   | <subquery-label>        : "{" { <fetch_query> | <get_aggregate_query>} "}"
  }; ...
```

#### Key Behaviors

- Returns lazy streams of JSON objects
- Supports rule-based inference
- Compatible with sorting and pagination modifiers
- May return fewer results than matched by `match` clause due to set semantics

#### Projection Types

**Direct Projection:**
```typeql
match
$f isa file, has path $p;
fetch
$p;
```

**Ownership Projection:**
```typeql
match
$p isa person;
fetch
$p: full-name, email;
```

**Subqueries:**
```typeql
match
$f isa file;
fetch
$f as file: path as filename;
file-size: {
    match $f has size-kb $sk;
    ?sm = round($sk / 1024);
    fetch ?sm as size-mb;
};
```

#### Output Customization

Use `as` keyword for relabeling keys in resulting JSON:

```typeql
fetch
$f as file: attribute as "all attributes";
```

#### Aggregated Values in Subqueries

```typeql
average-file-size: {
    match ($person,$acc) isa permission;
    $acc($file) isa access;
    $file isa file, has size-kb $size;
    get $size;
    mean $size;
};
```

#### Result Deduplication

A Fetch query can return fewer results than matched by its `match` clause. Due to set semantics, if fetch clause projects not every variable from the `match` clause, some results might lose their uniqueness and become redundant.

---

### Get Query

A Get query retrieves concepts as stateful objects from a TypeDB database for further processing via driver API methods.

#### Syntax

```typeql
match <pattern>
get [<variable> [, <variable>]];
```

#### Response Formats

| Scenario | Response Type |
|----------|---------------|
| Standard Get query | Stream/Iterator of ConceptMap |
| Get with aggregation | Promise of Value |
| Get with grouping | Stream/Iterator of ConceptMapGroup |
| Get with grouping and aggregation | Stream/Iterator of ValueGroup |

#### Key Characteristics

- Returns results in set semantics (no duplicates)
- ConceptMap objects map query variables to concept objects
- Supports sorting and pagination modifiers
- Enables rule-based inference

#### Examples

**Simple Example:**
```typeql
match
$p isa person,
    has full-name "Kevin Morrison",
    has email $e;
get $e;
```

**Complex Example with Modifiers:**
```typeql
match
$pe ($x, $y) isa permission;
$x isa person, has full-name $x-n;
$x-n contains "Kevin";
$y (object: $o, action: $act) isa access;
$act has name $act-n;
$o has path $o-fp;
get $x-n, $act-n, $o-fp;
sort $o-fp;
group $o-fp;
count;
```

---

## Patterns

A pattern is a set of declarative constraints. TypeQL uses patterns in its queries and clauses.

Patterns serve two primary functions:
- **Data queries**: Specify constraints on concepts to retrieve or process
- **Schema queries**: Define or undefine type definitions using schema-specific patterns

Patterns are designed to be composable—you can combine two patterns by merging their statements.

---

### Conjunction

A conjunction of patterns requires all its patterns to be true simultaneously.

#### Syntax

```typeql
<pattern>; <pattern>; [ <pattern>; ... ]
```

Conjunctions are applied implicitly to all patterns delineated by a semicolon.

#### Key Characteristics

- **Implicit application**: Conjunctions automatically connect all statements separated by semicolons
- **Logical requirement**: Every statement in the conjunction must evaluate to true
- **Order independence**: The ordering of statements in a conjunction is irrelevant

#### Example

```typeql
match
$user isa user, has full-name 'Kevin Morrison';
($user, $access) isa permission;
$obj isa object, has path $path;
$access($obj, $act) isa access;
$act isa action, has name 'modify_file';
fetch $path;
```

All six statements must simultaneously match for each valid solution to be returned.

---

### Disjunction (OR)

A disjunction represents "at least one of" logic in TypeQL patterns.

#### Syntax

```typeql
"{" <pattern> "}" or "{" <pattern> "}" [ or "{" <pattern> "}" ... ]
```

> At least one variable in the `<pattern>` must be bound outside the disjunction.

#### Core Behavior

Disjunctions function as patterns themselves and can appear in `match` clauses or rule conditions. When any branch of the disjunction matches, the solution is included in results.

#### Example

Pattern matching either `person` with `full-name` OR `file` with `path` attributes:

```typeql
match
{ $x isa person, has full-name $n; }
or
{ $x isa file, has path $n; };
fetch $x: attribute;
```

---

### Negation (NOT)

A negation of a pattern requires that pattern to be false. A negation is itself a pattern.

#### Syntax

```typeql
not "{" <pattern> "}" ;
```

> At least one variable within the negated pattern must be bound from outside the negation scope.

#### Core Behavior

A negation is true if its negated pattern is false. When implementing negations in rules, TypeDB applies stratified negation theory to manage logical dependencies and prevent circular reasoning.

#### Example: Excluding Results

```typeql
match
$u isa user;
not {$u has full-name "Kevin Morrison";};
```

#### Use in Rules

```typeql
rule permission-non-validity: when {
    $permission isa permission;
    not { $permission has validity true; };
} then {
    $permission has validity false;
};
```

#### Critical Limitation

Rules cannot create logical cycles with negation. Attempting to negate a condition and then assert its opposite violates stratified negation principles and produces an error.

---

## Statements

TypeQL statements form the fundamental building blocks of TypeQL patterns. Each statement terminates with a semicolon, and multiple statements automatically combine through conjunction.

### Statement Structure

Most simple statements follow a **Subject-Predicate-Object** pattern, where the predicate represents a TypeQL keyword.

**Composite Statements:** Multiple simple statements sharing the same subject can be consolidated:

```typeql
$p isa person, has full-name "Kevin Morrison", has email $e;
```

---

### isa / isa!

The `isa` keyword specifies a type for data instances, taking into account type inference. The `isa!` variant specifies only direct types, excluding subtypes.

#### Syntax

```typeql
<concept-variable> isa <type>;
```

#### Key Behavioral Differences

- **`isa` keyword**: Adds type constraints including all subtypes through type inference, enabling polymorphic matching
- **`isa!` keyword**: Applies the same constraint but excludes subtypes, requiring exact type matching

#### Usage Contexts

**In Match Patterns:**
```typeql
match
$attr isa attribute;  -- Returns all attribute instances
```

**In Insert Patterns:**
```typeql
insert
$p isa person, has full-name "Alice";
```

**In Delete Patterns:**
`isa` accepts both exact types and supertypes, while `isa!` requires exact type specification only.

---

### has

The `has` keyword indicates ownership relationships between data instances and their attributes.

#### Syntax

```typeql
<data-instance> has <attribute>;
```

#### Examples

**Match Patterns:**
```typeql
match
$p isa person, has full-name "Kevin Morrison", has email $e;
fetch $e;
```

**Insert Operations:**
```typeql
insert
$p has email "m.kevin@gmail.com";
```

When inserting with `has`, new attributes are implicitly created if they don't already exist.

**Delete Operations:**
Deleting ownership via `has` removes the link but preserves the attribute itself in the database.

---

### sub / sub!

The `sub` keyword specifies a parent type for a subtype. Use `sub!` to match only direct subtypes without type inference.

#### Syntax

```typeql
<subtype> sub <parent-type>;
```

#### Behavior Differences

- **In schema queries**: Both `sub` and `sub!` function identically
- **In data queries**: `sub` matches all existing subtypes; `sub!` matches only direct subtypes

#### Examples

**Schema Definition:**
```typeql
define
pdf sub file;
```

**Fetching All Subtypes:**
```typeql
match
$subtype sub subject;
fetch
$subtype;
```

**Fetching Direct Subtypes Only:**
```typeql
match
$type sub! subject;
fetch $type;
```

---

### owns

The `owns` keyword defines attribute ownership in TypeQL schemas.

#### Syntax

```typeql
<type> owns <attribute-type> [<annotation>] [as <overridden-type>];
```

Annotations include `@key` and `@unique`.

#### Examples

**Definition:**
```typeql
define pdf sub file, owns name;
```

**Removal:**
```typeql
undefine pdf owns name;
```

**Override Mechanism:**
```typeql
define
  name sub attribute, abstract, value string;
  full-name sub name;
  person sub entity, abstract, owns name;
  user sub person, owns full-name as name;
```

---

### relates

The `relates` keyword defines roles within relation types.

#### Syntax

```typeql
<relation-type> relates <role> [as overridden-type];
```

#### Example

```typeql
define
permission relates subject;
```

**Override Capability:**
```typeql
define
object-ownership sub ownership,
    owns ownership-type,
    relates object as owned;
```

---

### plays

The `plays` keyword defines which roles a type can occupy within relation types.

#### Syntax

```typeql
<type> plays <relation-type:role> [as overridden-type];
```

#### Example

```typeql
define
subject plays permission:subject;
```

**Override Functionality:**
```typeql
define
subject plays permission:manager as subject;
```

The overridden new role must be a subtype of the inherited role.

---

### rule

The `rule` keyword defines rule-based inference within a schema.

#### Syntax

```typeql
rule <rule-label>: when {
    <condition>
} then {
    <conclusion>
};
```

#### Key Characteristics

- Rules appear exclusively in Define queries
- Condition patterns accept any pattern similar to a `match` clause
- Conclusions must be single statements—either a `has` statement or an `isa` statement for relations with multiple roles
- The `rule` keyword adds a new rule or updates an existing rule with the same label

#### Example

```typeql
define
rule add-view-permission: when {
    $modify isa action, has name "modify_file";
    $view isa action, has name "view_file";
    $ac_modify (object: $obj, action: $modify) isa access;
    $ac_view (object: $obj, action: $view) isa access;
    (subject: $subj, access: $ac_modify) isa permission;
} then {
    (subject: $subj, access: $ac_view) isa permission;
};
```

**Removal:**
```typeql
undefine rule add-view-permission;
```

---

## Types and Concepts

### Type Hierarchy

TypeQL uses a polymorphic type system based on schema definitions. The system includes three built-in root types:

| Root Type | Subtype Purpose | Data Instance |
|-----------|-----------------|---------------|
| `entity` | Entity types | Entity |
| `relation` | Relation types | Relation |
| `attribute` | Attribute types | Attribute |

Root types are abstract types and need to be subtyped to use them.

#### Abstract Types

Abstract types cannot be instantiated with data but serve as templates for subtypes:

```typeql
subject sub entity, abstract;
```

#### Type Definition Pattern

Types inherit all properties from their supertypes:

```typeql
user sub entity,
    owns id @key,
    owns email,
    abstract;

person sub user, owns full-name;
```

---

### Concept Variables

Concept variables use a dollar sign followed by a label: `$<variable-label>`

Concept variables in TypeQL represent unknown types and data instances in data query patterns. When TypeDB solves a pattern, each solution pairs variables with matching concepts.

#### Type Restrictions

TypeQL statements create implicit type constraints through inference:

- Operations like `sub`, `type`, and `owns` apply only to types
- `isa`, `has`, and `is` work exclusively with data instances
- Value operations (arithmetic, comparators, functions) apply solely to attributes

#### Examples

**Basic Attribute Retrieval:**
```typeql
match $x has $a;
fetch $a;
```

**Type Variablization:**
```typeql
match $x isa person, has $a; $a isa! $type;
fetch $type;
```

---

## Values

### Value Types

TypeQL supports five primitive value types:

| Type | Description |
|------|-------------|
| **boolean** | Literals: `true` and `false` |
| **long** | 64-bit signed integer |
| **double** | 64-bit floating-point number |
| **string** | Variable length UTF-8 encoded string up to 64 kB, enclosed in single or double quotes |
| **datetime** | Millisecond-precision timestamp without timezone |

#### DateTime Format Options

- `yyyy-mm-dd`
- `yyyy-mm-ddThh:mm`
- `yyyy-mm-ddThh:mm:ss`
- `yyyy-mm-ddThh:mm:ss.fff`

Regardless of the representation in the query, datetimes are always padded to millisecond precision when stored.

#### Schema Definition

```typeql
define
full-name sub attribute, value string;
review-date sub attribute, value datetime;
size-kb sub attribute, value long;
percentage sub attribute, value double;
validity sub attribute, value boolean;
```

---

### Comparators

Comparators are used within `match` clauses to compare values. Comparators are always considered to return True, setting a constraint on values.

#### Basic Comparison Operators

| Operator | Meaning |
|----------|---------|
| `==` | equality |
| `!=` | inequality |
| `>` | greater than |
| `>=` | greater than or equal |
| `<` | less than |
| `<=` | less than or equal |

#### Examples

**Equality:**
```typeql
$size == 100;
```

**Inequality:**
```typeql
$filepath != "README.md";
```

**Range Comparisons:**
```typeql
$size <= 100;
```

#### String-Specific Comparators

**Contains:** Case-insensitive substring matching
```typeql
$name contains "Kevin";
```

**Like:** Pattern matching using regular expressions
```typeql
$name like "^(Kevin Morrison|Pearle Goodman)$";
```

> Note: The single equals sign (`=`) for comparison was deprecated in TypeDB 2.18.0 in favor of `==`.

---

### Arithmetic

TypeQL supports arithmetic expressions to compute values dynamically within queries.

#### Syntax

```typeql
?variable = expression;
```

Example: `?x = $s + 1;`

#### Operations (Order of Precedence)

1. **Parentheses** `()` — grouping expressions
2. **Exponentiation** `^` — power operations
3. **Multiplication** `*`
4. **Division** `/`
5. **Modulo** `%` — remainder of division
6. **Addition** `+`
7. **Subtraction** `-`

#### Example

```typeql
?gb = (($s + ?o) / 1024) / 1024;
```

This calculates gigabytes by taking a concept variable, adding a value variable, then dividing by 1024 twice.

---

### Built-in Functions

#### Min/Max Functions

```typeql
?maximum = max(100, $x, ?a);
?minimum = min(100, $x, ?a);
```

#### Ceil/Floor Functions

```typeql
?int = floor(100.7);
?int = ceil(100.7);
```

#### Round Function

```typeql
?int = round(100.7);
```

Rounds the input value up to a closest integer (half-way up).

#### Abs Function

```typeql
?x = abs($s - 1000);
```

Computes the absolute value of an input expression.

---

## Query Modifiers

Modifiers let you process the results of a query. By using modifiers, you can change ordering, number of results, or even the output format.

Modifiers are positioned at the end of queries, after all clauses.

---

### Sorting

Use the `sort` keyword to order query results. By default, results stream without guaranteed order.

#### Syntax

Use `sort` followed by one or more comma-separated variables, with optional `asc` (ascending, default) or `desc` (descending) modifiers.

#### Examples

**Fetch Query:**
```typeql
match
$p isa person, has full-name $n;
fetch
$p: full-name;
sort $n asc;
```

**Get Query:**
```typeql
match
$p isa person, has full-name $n;
get $n;
sort $n desc;
```

> Variables used in `sort` don't require inclusion in the `fetch` clause.

---

### Pagination

Pagination enables retrieving query results in manageable batches using `offset` and `limit`.

> Pagination relies on sorting to traverse the full set of results.

#### Offset

Skip a specified number of results:
```typeql
match
$p isa person, has full-name $n;
get $n;
sort $n;
offset 2;
```

#### Limit

Restrict the number of returned results:
```typeql
match
$p isa person, has full-name $n;
get $n;
limit 2;
```

#### Combined Pagination Pattern

**Query 1** (initial batch):
```typeql
sort $n;
limit 2;
```

**Query 2** (subsequent batch):
```typeql
sort $n;
offset 2;
limit 2;
```

**Iteration Strategy**: Increment the offset by the limit value with each query. When returned results fall below the specified limit, all data has been retrieved.

---

### Aggregation

TypeQL provides seven aggregation operations for Get query results:

| Function | Description |
|----------|-------------|
| `count` | Get the total number of results returned |
| `sum` | Total `long` or `double` values from a specified variable |
| `max` | Get the maximum value among `long` or `double` values |
| `min` | Get the minimum value among `long` or `double` values |
| `mean` | Compute the average of numeric values |
| `median` | Get the median value among `long` or `double` values |
| `std` | Get the sample standard deviation value |

#### Core Behavior

Without aggregation, Get queries return a stream of ConceptMaps. When aggregation is applied, the query performs calculation on the collection and returns a single value.

#### Example

```typeql
match
$p isa person;
get $p;
count;
```

---

### Grouping

Grouping organizes query results based on specified variables.

#### Syntax

```typeql
match
$p isa person, has full-name $n, has email $e;
get;
group $p;
```

#### Core Functionality

Results are partitioned so that instances with matching values for the grouped variable appear together.

**Aggregation Integration:**
```typeql
match
$p isa person, has $a;
get;
group $a;
count;
```

This returns a count for each distinct attribute value.

---

## Keywords Reference

### Clause Keywords

| Keyword | Purpose |
|---------|---------|
| `define` | Begins a Define query for schema creation |
| `undefine` | Begins an Undefine query for schema removal |
| `match` | Starts pattern matching |
| `insert` | Begins an Insert query for data addition |
| `delete` | Begins a Delete query for data removal |
| `fetch` | Begins a Fetch query for data retrieval |
| `get` | Begins a Get query for data retrieval |

### Schema Statement Keywords

| Keyword | Purpose |
|---------|---------|
| `sub` / `sub!` | Constrains a type as a subtype (direct or indirect) |
| `type` | Constrains an exact type by label |
| `abstract` | Declares a type as abstract |
| `owns` | Specifies attribute ownership capabilities |
| `value` | Defines attribute value types |
| `relates` | Adds roles to relations |
| `plays` | Declares role-playing capabilities |
| `@key` | Applies key constraints to attributes |
| `@unique` | Applies uniqueness constraints |
| `regex` | Restricts attribute values via regular expressions |
| `as` | Overrides inherited ownership or role abilities |
| `when` / `then` | Specify rule conditions and conclusions |

### Data Statement Keywords

| Keyword | Purpose |
|---------|---------|
| `isa` / `isa!` | Constrains instance type (with or without inference) |
| `is` | Equates two concept variables |
| `has` | Constrains attribute ownership |

### Modifier Keywords

**Pagination & Sorting:**
- `offset`, `limit`, `sort`

**Logic:**
- `or` — Disjunctions between statement blocks
- `not` — Negates statement blocks

**Comparators:**
- `==`, `!=`, `>`, `<`, `>=`, `<=`, `like`, `contains`

**Aggregation:**
- `group`, `count`, `max`, `min`, `mean`, `median`, `std`, `sum`

---

## Python Driver

### Installation

**Supported versions:** Python 3.8 to 3.11 (Linux requires glibc 2.25.0+)

```bash
pip install typedb-driver
```

> Note: Versions prior to 2.24.0 used `pip install typedb-client`

### Verification

```python
import typedb.driver
```

### Quick Start Example

```python
from typedb.driver import TypeDB, SessionType, TransactionType

DB_NAME = "access-management-db"
SERVER_ADDR = "127.0.0.1:1729"

with TypeDB.core_driver(SERVER_ADDR) as driver:
    # Database management
    if driver.databases.contains(DB_NAME):
        driver.databases.get(DB_NAME).delete()
    driver.databases.create(DB_NAME)

    # Schema operations
    with driver.session(DB_NAME, SessionType.SCHEMA) as session:
        with session.transaction(TransactionType.WRITE) as tx:
            tx.query.define("define person sub entity;")
            tx.query.define("define name sub attribute, value string; person owns name;")
            tx.commit()

    # Data operations
    with driver.session(DB_NAME, SessionType.DATA) as session:
        # Write data
        with session.transaction(TransactionType.WRITE) as tx:
            tx.query.insert("insert $p isa person, has name 'Alice';")
            tx.commit()

        # Read data
        with session.transaction(TransactionType.READ) as tx:
            results = tx.query.fetch("match $p isa person; fetch $p: name;")
            for json in results:
                print(json)
```

### Key Capabilities

- **Database Management:** Creating, deleting, and retrieving databases
- **Schema Operations:** Defining entity types, attributes, and relationships
- **Data Manipulation:** Inserting, querying, and fetching data
- **Transaction Support:** Read and write transaction handling
- **Session Management:** SCHEMA and DATA session types

### Session Types

| Session Type | Purpose |
|--------------|---------|
| `SessionType.SCHEMA` | For schema definition operations (define, undefine) |
| `SessionType.DATA` | For data operations (insert, delete, update, fetch, get) |

### Transaction Types

| Transaction Type | Purpose |
|------------------|---------|
| `TransactionType.READ` | Read-only transactions |
| `TransactionType.WRITE` | Write transactions (require commit) |

### Version Compatibility

Latest stable version: 2.28.0 compatible with TypeDB 2.28.0 and Python 3.8–3.11

---

## Session and Transaction Requirements

### Schema Queries

- **Session type:** `SCHEMA`
- **Transaction type:** `WRITE`
- **Queries:** Define, Undefine

### Data Read Queries

- **Session type:** `DATA`
- **Transaction type:** `READ`
- **Queries:** Fetch, Get (with inference support)

### Data Write Queries

- **Session type:** `DATA`
- **Transaction type:** `WRITE`
- **Queries:** Insert, Delete, Update

> Important: Unlike schema definition queries, writing data queries are not idempotent. Running the same query twice might result in undesirable results, like duplicating data.

---

## Complete Schema Example

```typeql
define

# Attribute types
credential sub attribute, value string;
email sub attribute, value string;
full-name sub attribute, value string;
name sub attribute, value string;
path sub attribute, value string;
review-date sub attribute, value datetime;
size-kb sub attribute, value long;
validity sub attribute, value boolean;

# Entity types
subject sub entity,
    abstract,
    owns credential,
    plays permission:subject;

user sub subject, abstract;

person sub user,
    owns email,
    owns full-name;

object sub entity,
    abstract,
    owns path,
    plays access:object;

file sub object,
    owns size-kb;

action sub entity,
    owns name,
    plays access:action;

# Relation types
access sub relation,
    relates object,
    relates action;

permission sub relation,
    owns review-date,
    owns validity,
    relates subject,
    relates access;

# Rules
rule add-view-permission: when {
    $modify isa action, has name "modify_file";
    $view isa action, has name "view_file";
    $ac_modify (object: $obj, action: $modify) isa access;
    $ac_view (object: $obj, action: $view) isa access;
    (subject: $subj, access: $ac_modify) isa permission;
} then {
    (subject: $subj, access: $ac_view) isa permission;
};
```

---

## Database Export and Import

TypeDB 2.x (since 2.19.0) supports full database export and import via the server CLI. This produces a schema file (TypeQL) and a binary data file that can be imported into another TypeDB instance running the same version.

### Export

```bash
typedb server export \
    --database=<database-name> \
    --port=<port> \
    --schema=<schema-output-file>.typeql \
    --data=<data-output-file>.typedb
```

**Example (Docker):**
```bash
# Export from inside the container (write to a writable path like /tmp)
docker exec alhazen-typedb /opt/typedb-all-linux-x86_64/typedb server export \
    --database=alhazen_notebook \
    --port=1729 \
    --schema=/tmp/alhazen_notebook_schema.typeql \
    --data=/tmp/alhazen_notebook_data.typedb

# Copy files out of the container
docker cp alhazen-typedb:/tmp/alhazen_notebook_schema.typeql ./alhazen_notebook_schema.typeql
docker cp alhazen-typedb:/tmp/alhazen_notebook_data.typedb ./alhazen_notebook_data.typedb
```

**Output:**
- Schema file (`.typeql`) — human-readable TypeQL define statements
- Data file (`.typedb`) — binary format containing all entity/relation/attribute instances

### Import

The target database must **not already exist**. TypeDB creates it during import.

```bash
typedb server import \
    --database=<database-name> \
    --port=<port> \
    --schema=<schema-file>.typeql \
    --data=<data-file>.typedb
```

**Example (Docker):**
```bash
# Copy files into the container
docker cp ./alhazen_notebook_schema.typeql alhazen-typedb:/tmp/alhazen_notebook_schema.typeql
docker cp ./alhazen_notebook_data.typedb alhazen-typedb:/tmp/alhazen_notebook_data.typedb

# Import (database must not exist yet)
docker exec alhazen-typedb /opt/typedb-all-linux-x86_64/typedb server import \
    --database=alhazen_notebook \
    --port=1729 \
    --schema=/tmp/alhazen_notebook_schema.typeql \
    --data=/tmp/alhazen_notebook_data.typedb
```

### Important Notes

- **Version compatibility:** Export and import must use the same TypeDB version. The binary data format is version-specific.
- **Write path:** When running in Docker, the schema volume mount (`/data` or `/schema`) may be read-only. Use `/tmp` or another writable path for export output.
- **Full database only:** There is no built-in way to export a subset of data. To export a subset, use TypeQL fetch queries via the Python driver and generate insert statements.
- **No overwrite:** Import requires the target database to not exist. Drop the existing database first if re-importing: `database delete <name>` in the TypeDB console.

---

*Document compiled from TypeDB 2.x official documentation.*
