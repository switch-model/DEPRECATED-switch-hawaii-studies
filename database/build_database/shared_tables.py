from util import execute

queries = {}

# note: some of the project data could go in a separate site table,
# but we keep it all in one place for now for simplicity
# ??? can we add existing projects to this table too? (no reason not to;
# may need to add a flag indicating whether more capacity can be built in
# each project.)
# note: we assume max_capacity indicates the max amount of each technology
# if that is the only thing built at this site; if multiple projects
# are built on the same site, we require sum(Build[site, tech]/max_capacity[site, tech]) <= 1.
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
        project_id INT NOT NULL,
        date_time TIMESTAMP WITH TIME ZONE,
        cap_factor REAL
    );
    ALTER TABLE cap_factor OWNER TO admin;
"""
# queries[("cap_factor", "create_indexes")] = """
#     DO $$
#     BEGIN
#         BEGIN
#             ALTER TABLE cap_factor
#                 ADD CONSTRAINT pt PRIMARY KEY (project_id, date_time),
#                 ADD CONSTRAINT tp UNIQUE (date_time, project_id)
#         EXCEPTION
#             WHEN duplicate_object THEN NULL; -- ignore if index exists already
#         END;
#     END $$;
# """
queries[("cap_factor", "create_indexes")] = """
    ALTER TABLE cap_factor
        ADD CONSTRAINT pt PRIMARY KEY (project_id, date_time),
        ADD CONSTRAINT tp UNIQUE (date_time, project_id)
"""
queries[("cap_factor", "drop_indexes")] = """
    ALTER TABLE cap_factor 
        DROP CONSTRAINT IF EXISTS pt,
        DROP CONSTRAINT IF EXISTS tp
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

# TODO: write this
def calculate_interconnect_distances():
    """Choose closest interconnect location to each project, and calculate distance to it.
    Also calculate connect_cost_per_mw based on distance and interconnect. (Or maybe we
    should drop that column and calculate connect costs during data export based on the
    interconnect's cost per mw and the project's distance to the interconnect.)
    """
    raise NotImplemented
    execute("""
        
    """)