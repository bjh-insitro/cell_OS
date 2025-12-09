import { useState, useEffect } from 'react';

type Theme = 'light' | 'dark' | 'system';

export function useTheme() {
    const [theme, setTheme] = useState<Theme>(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('theme');
            if (saved === 'light' || saved === 'dark' || saved === 'system') {
                return saved;
            }
        }
        return 'system';
    });

    useEffect(() => {
        const root = window.document.documentElement;

        const applyTheme = (t: Theme) => {
            root.classList.remove('light', 'dark');

            if (t === 'system') {
                const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                root.classList.add(systemTheme);
            } else {
                root.classList.add(t);
            }
        };

        applyTheme(theme);
        localStorage.setItem('theme', theme);

        if (theme === 'system') {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            const handleChange = () => {
                root.classList.remove('light', 'dark');
                root.classList.add(mediaQuery.matches ? 'dark' : 'light');
            };

            mediaQuery.addEventListener('change', handleChange);
            return () => mediaQuery.removeEventListener('change', handleChange);
        }
    }, [theme]);

    return { theme, setTheme };
}
