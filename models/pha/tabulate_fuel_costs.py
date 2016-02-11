import os
from collections import defaultdict

n_digits = 4    # number of digits used in filenames
n_scenarios = 117
inputs_dir = "inputs"
inputs_subdir = "pha_117"

values = defaultdict(list)

for x in range(n_scenarios):
    with open(os.path.join(
            inputs_dir, inputs_subdir, "fuel_supply_curves_{}.dat".format(str(x).zfill(n_digits))
        )
    ) as f:
        rows = [r.split("\t") for r in f.read().split('\n')][1:-2]   # omit header row and semicolon at end
        for r in rows:
            
            key = r[0]
            if r[2] != "base":
                key += r[2]
            values[(key, r[1])].append(r[3])

with open(os.path.join(inputs_dir, inputs_subdir, "fuel_supply_costs.tsv"), "w") as f:
    f.write("fuel\tyear\tprice_per_mmbtu\n")
    f.writelines(
        "\t".join(list(k) + map(str, values[k])) + "\n"
            for k in sorted(values.keys())
    )
