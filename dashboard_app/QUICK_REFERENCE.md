# Dashboard Quick Reference

## 🚀 Quick Start

### Run the Dashboard
```bash
streamlit run dashboard_app/app.py
```

### Test the Refactoring
```bash
python3 dashboard_app/test_refactoring.py
```

---

## ➕ Adding a New Page (Quick Guide)

### 1. Create Page Module
```python
# dashboard_app/pages/tab_my_feature.py
import streamlit as st

def render_my_feature(df, pricing):
    """Render the My Feature page."""
    st.header("My Feature")
    st.write("Your content here")
    
    # Access data
    if not df.empty:
        st.dataframe(df)
    
    # Access pricing
    items = pricing.get("items", {})
    st.write(f"Found {len(items)} items in inventory")
```

### 2. Register Page
```python
# In dashboard_app/config.py, inside create_page_registry():

# Add import at top
from dashboard_app.pages.tab_my_feature import render_my_feature

# Add registration (in appropriate category section)
registry.register(PageConfig(
    key="my_feature",                    # Unique identifier
    title="My Feature",                  # Display name (no emoji)
    emoji="🎯",                          # Page emoji
    render_function=render_my_feature,   # Your render function
    category=PageCategory.CORE,          # Choose category
    description="What this page does",   # Optional description
    order=10                             # Order within category
))
```

### 3. Done! ✨
That's it! The page will automatically appear in the navigation.

---

## 📂 File Structure

```
dashboard_app/
├── app.py                      # Main entry point
├── config.py                   # Page registry (edit to add pages)
├── utils.py                    # Shared utilities
├── test_refactoring.py         # Validation tests
├── README.md                   # Architecture docs
├── MIGRATION.md                # Migration guide
├── BEFORE_AFTER.md             # Comparison
├── REFACTORING_SUMMARY.md      # Summary
└── pages/                      # Page modules
    ├── tab_*.py                # Individual pages
    └── *.py                    # Other pages
```

---

## 🏷️ Page Categories

Choose the appropriate category when registering a page:

| Category | Purpose | Examples |
|----------|---------|----------|
| `PageCategory.CORE` | Essential dashboard pages | Mission Control, Science, Economics |
| `PageCategory.SIMULATION` | Simulation tools | POSH Campaign Sim, Workflow Visualizer |
| `PageCategory.AUDIT` | Inspection & auditing | Resource Audit, Cell Line Inspector |
| `PageCategory.PLANNING` | Planning & management | Inventory, Campaign Manager |
| `PageCategory.ANALYSIS` | Analytics & reports | Analytics, Campaign Reports |

---

## 🔧 Common Tasks

### Change Page Order
Edit the `order` parameter in `config.py`:
```python
registry.register(PageConfig(
    # ...
    order=1  # Lower numbers appear first
))
```

### Change Page Category
Edit the `category` parameter in `config.py`:
```python
registry.register(PageConfig(
    # ...
    category=PageCategory.PLANNING  # Move to Planning category
))
```

### Remove a Page
Comment out or delete the `registry.register()` call in `config.py`.

### Rename a Page
Edit the `title` and/or `emoji` in `config.py`:
```python
registry.register(PageConfig(
    # ...
    title="New Name",
    emoji="🆕"
))
```

---

## 📝 Page Module Template

```python
"""
Brief description of what this page does.
"""
import streamlit as st
import pandas as pd


def render_my_page(df: pd.DataFrame, pricing: dict):
    """
    Render the My Page interface.
    
    Args:
        df: DataFrame with simulation/execution data
        pricing: Dictionary with pricing/inventory data
    """
    # Page header
    st.header("My Page Title")
    
    # Optional description
    st.markdown("""
    This page does X, Y, and Z.
    """)
    
    # Main content
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Section 1")
        # Your content
        
    with col2:
        st.subheader("Section 2")
        # Your content
    
    # Data visualization
    if not df.empty:
        st.subheader("Data")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No data available")
```

---

## 🧪 Testing Your Page

### Manual Test
1. Run `streamlit run dashboard_app/app.py`
2. Navigate to your page in the sidebar
3. Verify it renders correctly

### Automated Test
```bash
python3 dashboard_app/test_refactoring.py
```

Should show:
```
✓ Total pages registered: 18  # (17 + your new page)
✅ All tests passed!
```

---

## 🐛 Troubleshooting

### Page doesn't appear in navigation
- ✅ Check that you called `registry.register()` in `config.py`
- ✅ Check that the import statement is correct
- ✅ Restart Streamlit (Ctrl+C and re-run)

### Import error
- ✅ Check file path: `dashboard_app/pages/tab_*.py`
- ✅ Check function name matches import
- ✅ Check for typos in import statement

### Page renders but shows error
- ✅ Check render function signature: `def render_*(df, pricing)`
- ✅ Check for exceptions in your code
- ✅ Look at Streamlit error message

### Page appears in wrong category
- ✅ Check `category` parameter in `PageConfig`
- ✅ Make sure you're using `PageCategory.XXXX` enum

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| `README.md` | Architecture overview and how-to guides |
| `MIGRATION.md` | Migration guide and before/after |
| `BEFORE_AFTER.md` | Detailed comparison |
| `REFACTORING_SUMMARY.md` | Executive summary |
| `ARCHITECTURE.txt` | Visual architecture diagram |
| `QUICK_REFERENCE.md` | This file! |

---

## 💡 Tips

- **Keep pages focused**: Each page should do one thing well
- **Use descriptive names**: Make it clear what the page does
- **Add descriptions**: Help users understand the page purpose
- **Order matters**: Lower order numbers appear first in category
- **Test your changes**: Run the test script before committing
- **Follow the template**: Use the page module template above

---

## 🎯 Best Practices

1. **One page = one file**: Keep pages in separate modules
2. **Consistent naming**: Use `tab_*` prefix for page files
3. **Document your code**: Add docstrings to render functions
4. **Handle empty data**: Check if `df.empty` before using
5. **Use columns**: Organize content with `st.columns()`
6. **Add error handling**: Wrap risky operations in try/except
7. **Test thoroughly**: Verify with different data states

---

## 🚀 Next Steps

After adding your page:
1. ✅ Test it manually in the dashboard
2. ✅ Run automated tests
3. ✅ Add documentation if needed
4. ✅ Commit your changes
5. ✅ Update CHANGELOG if applicable

---

**Need more help?** See `README.md` for detailed documentation.
