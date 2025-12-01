# Dashboard Architecture

## Overview

The cell_OS dashboard has been refactored to use a **registry-based architecture** that makes it easy to add, remove, and organize pages without modifying the core application logic.

## Key Components

### 1. `app.py` - Main Application
The main entry point that:
- Sets up the Streamlit page configuration
- Loads data using `utils.load_data()`
- Creates the page registry
- Renders the sidebar navigation
- Routes to the selected page

**Key functions:**
- `setup_page()` - Configure Streamlit settings
- `render_sidebar()` - Build navigation UI
- `render_page()` - Route to and render the selected page
- `main()` - Application entry point

### 2. `config.py` - Page Registry
Centralized configuration for all dashboard pages.

**Key classes:**
- `PageCategory` - Enum defining page categories (Core, Simulation, Audit, Planning, Analysis)
- `PageConfig` - Dataclass holding page metadata (title, emoji, render function, etc.)
- `PageRegistry` - Registry managing all pages with lookup and organization methods
- `create_page_registry()` - Factory function that registers all pages

### 3. `utils.py` - Shared Utilities
Common utilities used across the dashboard (data loading, etc.)

### 4. `pages/` - Page Modules
Individual page implementations, each with a `render_*()` function.

## Adding a New Page

To add a new page to the dashboard:

1. **Create the page module** in `dashboard_app/pages/`:
   ```python
   # dashboard_app/pages/tab_my_new_page.py
   import streamlit as st
   
   def render_my_new_page(df, pricing):
       st.header("My New Page")
       # Your page implementation here
   ```

2. **Register the page** in `config.py`:
   ```python
   # In create_page_registry() function
   from dashboard_app.pages.tab_my_new_page import render_my_new_page
   
   registry.register(PageConfig(
       key="my_new_page",
       title="My New Page",
       emoji="🎯",
       render_function=render_my_new_page,
       category=PageCategory.CORE,  # or another category
       description="Description of what this page does",
       order=10  # Controls ordering within category
   ))
   ```

That's it! No need to modify `app.py` or add any if-elif statements.

## Page Categories

Pages are organized into categories for better navigation:

- **Core** - Essential dashboard pages (Mission Control, Science, Economics)
- **Simulation** - Simulation and workflow tools
- **Audit** - Inspection and auditing tools
- **Planning** - Planning and management tools
- **Analysis** - Analytics and reporting tools

## Benefits of This Architecture

### ✅ Maintainability
- Single source of truth for page configuration
- No more long if-elif chains
- Easy to see all pages at a glance

### ✅ Scalability
- Add new pages without touching core routing logic
- Organize pages by category automatically
- Control page ordering with simple `order` parameter

### ✅ Flexibility
- Easy to add metadata to pages (descriptions, permissions, etc.)
- Can implement advanced features like:
  - Page search
  - Favorites
  - Recently viewed
  - Role-based access control
  - Page-specific settings

### ✅ Testability
- Page registry can be tested independently
- Mock pages easily for testing
- Clear separation of concerns

## Migration Notes

The refactored `app.py` maintains full backward compatibility with all existing page modules. All pages continue to receive `(df, pricing)` as arguments.

### What Changed
- ❌ Removed: Long if-elif chain (17 conditions)
- ❌ Removed: Hardcoded page titles and emojis scattered in code
- ✅ Added: `PageRegistry` system
- ✅ Added: Category-based organization
- ✅ Added: Centralized page configuration
- ✅ Improved: Error handling for page rendering
- ✅ Improved: Sidebar navigation with better UX

### What Stayed the Same
- All existing page modules work without changes
- Data loading mechanism unchanged
- Page render function signatures unchanged
- Streamlit configuration unchanged

## Future Enhancements

Potential improvements enabled by this architecture:

1. **Page Search** - Add search functionality to quickly find pages
2. **Favorites** - Let users mark favorite pages for quick access
3. **Breadcrumbs** - Show navigation history
4. **Page Permissions** - Add role-based access control
5. **Dynamic Loading** - Lazy load page modules for faster startup
6. **Page Analytics** - Track which pages are most used
7. **Custom Layouts** - Different layouts for different page types
8. **Page Settings** - Per-page configuration options

## Code Metrics

### Before Refactoring
- Lines of code: 155
- Cyclomatic complexity: ~18 (one if-elif per page)
- Pages: 17 hardcoded conditions
- Maintainability: Low (must edit main file for every page)

### After Refactoring
- Lines of code: ~160 (app.py) + ~280 (config.py) = ~440 total
- Cyclomatic complexity: ~5 (main routing logic)
- Pages: 17 registered in config
- Maintainability: High (add pages without touching routing)

While total lines increased, the code is now much more maintainable and scalable.
