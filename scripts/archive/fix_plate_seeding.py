"""
Fix plate/day/operator factor seeding to include run_context.seed.

Currently these factors are constant across runs, which means "cursed day"
is deterministic globally. They should vary by run_context so each experimental
run can have different batch effects.
"""

import re

# Read the file
with open('/Users/bjh/cell_OS/src/cell_os/hardware/biological_virtual.py', 'r') as f:
    content = f.read()

# Pattern 1: plate factor
old_pattern_plate = r'rng_plate = np\.random\.default_rng\(stable_u32\(f"plate_\{plate_id\}"\)\)'
new_pattern_plate = r'rng_plate = np.random.default_rng(stable_u32(f"plate_{self.run_context.seed}_{batch_id}_{plate_id}"))'

# Pattern 2: day factor
old_pattern_day = r'rng_day = np\.random\.default_rng\(stable_u32\(f"day_\{day\}"\)\)'
new_pattern_day = r'rng_day = np.random.default_rng(stable_u32(f"day_{self.run_context.seed}_{batch_id}_{day}"))'

# Pattern 3: operator factor
old_pattern_operator = r'rng_operator = np\.random\.default_rng\(stable_u32\(f"operator_\{operator\}"\)\)'
new_pattern_operator = r'rng_operator = np.random.default_rng(stable_u32(f"op_{self.run_context.seed}_{batch_id}_{operator}"))'

# Apply replacements
content = re.sub(old_pattern_plate, new_pattern_plate, content)
content = re.sub(old_pattern_day, new_pattern_day, content)
content = re.sub(old_pattern_operator, new_pattern_operator, content)

# Count replacements
plate_count = content.count('rng_plate = np.random.default_rng(stable_u32(f"plate_{self.run_context.seed}')
day_count = content.count('rng_day = np.random.default_rng(stable_u32(f"day_{self.run_context.seed}')
op_count = content.count('rng_operator = np.random.default_rng(stable_u32(f"op_{self.run_context.seed}')

print(f"Replacements made:")
print(f"  Plate factors: {plate_count}")
print(f"  Day factors: {day_count}")
print(f"  Operator factors: {op_count}")

# Write back
with open('/Users/bjh/cell_OS/src/cell_os/hardware/biological_virtual.py', 'w') as f:
    f.write(content)

print("\nFix applied successfully!")
print("Plate/day/operator factors now include run_context.seed and batch_id.")
print("This ensures 'cursed day' varies per run, not globally constant.")
