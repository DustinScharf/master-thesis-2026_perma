"""Import da Silva's stored extractions into isolated, provenance-aware graphs.

The historical database is never migrated in place. Existing partitions may only
be reused when both their source fingerprint and their complete graph agree.
"""

import argparse
import os

from neo4j import GraphDatabase

from graph_model import BACKLOGS, MODELS, generate_clean_id, load_partitions
from graph_database import initialize_schema, import_partition, validate_schema


DEFAULT_DATABASE = "userstories-review"


def connection_arguments(parser):
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    database_group = parser.add_mutually_exclusive_group()
    database_group.add_argument("--database", default=DEFAULT_DATABASE)
    database_group.add_argument(
        "--separate-databases",
        action="store_true",
        help="Use one physical Neo4j database per backlog (database names g03 and g04).",
    )
    parser.add_argument("--model", choices=MODELS, default="gpt-4-turbo")
    parser.add_argument("--backlog", choices=BACKLOGS, nargs="+", default=list(BACKLOGS))
    return parser


def database_for_backlog(args, pid):
    database = pid if getattr(args, "separate_databases", False) else args.database
    if database.lower() in {"userstories", "system"}:
        raise ValueError("Use a separate review database; the historical userstories database is protected.")
    return database


def connect(args):
    for pid in args.backlog:
        database_for_backlog(args, pid)
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD must be set as an environment variable.")
    return GraphDatabase.driver(args.uri, auth=(args.user, password))


def main(argv=None):
    parser = connection_arguments(argparse.ArgumentParser(description=__doc__))
    parser.add_argument("--input-root", help="Extraction directory; default: evaluation/extracted_data")
    args = parser.parse_args(argv)
    if len(args.backlog) != len(set(args.backlog)):
        parser.error("Each backlog may only be selected once")
    # Validate every selected file before opening a database connection.
    partitions = load_partitions(args.model, args.backlog, args.input_root)
    with connect(args) as driver:
        for partition in partitions:
            database = database_for_backlog(args, partition["pid"])
            with driver.session(database=database) as session:
                validate_schema(session)
                initialize_schema(session)
                imported = session.execute_write(import_partition, partition)
                print(
                    f"{partition['model']}/{partition['pid']} -> {database}: "
                    f"{len(partition['records'])} story nodes; "
                    f"{partition['source_record_count']} input records; "
                    f"{partition['duplicate_source_records']} identical input records coalesced; "
                    f"{'imported' if imported else 'already present and exactly verified'}."
                )
                validate_schema(session)


if __name__ == "__main__":
    main()
