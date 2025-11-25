from cell_os.unit_ops import AssayRecipe, UnitOp

print("Imported AssayRecipe:", AssayRecipe)
print("AssayRecipe fields:", AssayRecipe.__dataclass_fields__.keys())

try:
    recipe = AssayRecipe(name="Test", ops=[])
    print("Successfully created recipe:", recipe)
except TypeError as e:
    print("Failed to create recipe:", e)
