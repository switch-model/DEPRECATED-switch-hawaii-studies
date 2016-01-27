from util import execute

queries = {}
# note: some of the project data could go in a separate site table,
# but we keep it all in one place for now for simplicity
queries[("project", "create_table")] = """
    CREATE TABLE IF NOT EXISTS project (
        project_id SERIAL PRIMARY KEY,
        load_zone VARCHAR(20),
        technology VARCHAR(50),
        site VARCHAR(20),
        orientation VARCHAR(5),
        max_capacity REAL,
        latitude REAL,
        longitude REAL,
        interconnect_id INT,
        connect_distance_km REAL,
        connect_cost_per_mw REAL
    );
    ALTER TABLE project OWNER TO admin;
"""
queries[("cap_factor", "create_table")] = """
    CREATE TABLE IF NOT EXISTS cap_factor (
        project_id INT,
        date_time TIMESTAMP WITH TIME ZONE,
        cap_factor REAL,
    );
    ALTER TABLE cap_factor OWNER TO admin;
"""
queries[("cap_factor", "create_indexes")] = """
    DO $$
    BEGIN
        BEGIN
            ALTER TABLE cap_factor 
                ADD CONSTRAINT ztsod PRIMARY KEY (load_zone, technology, site, orientation, date_time),
                ADD CONSTRAINT dztso UNIQUE (date_time, load_zone, technology, site, orientation)
        EXCEPTION
            WHEN duplicate_object THEN NULL; -- ignore duplicate constraints
        END;
    END $$;
"""
queries[("cap_factor", "drop_indexes")] = """
    ALTER TABLE cap_factor 
        DROP CONSTRAINT IF EXISTS ztsod,
        DROP CONSTRAINT IF EXISTS dztso
"""

def create_table(table):
    execute(queries[(table, "create_table")])
    create_indexes(table)

def create_indexes(table):
    if (table, "create_indexes") in queries:
        execute(queries[(table, "create_indexes")])

def drop_indexes(table):
    if (table, "drop_indexes") in queries:
        execute(queries[(table, "drop_indexes")])

def calculate_interconnect_distances():
    """Choose closest interconnect location to each project, and calculate distance to it."""
    raise NotImplemented
    execute("""
        
    """)