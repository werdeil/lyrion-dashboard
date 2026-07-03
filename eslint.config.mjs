// Lints the hand-written page scripts only; static/lib/ holds vendored
// minified libraries (Vibrant, FastAverageColor) that are not ours to lint.
// Rules are declared inline (rather than extending @eslint/js recommended) so
// the config has no dependency and runs with a bare `npx eslint`.
export default [
    {
        files: ["static/*.js"],
        languageOptions: {
            ecmaVersion: 2021,
            sourceType: "script",
            globals: {
                window: "readonly",
                document: "readonly",
                navigator: "readonly",
                localStorage: "readonly",
                fetch: "readonly",
                setInterval: "readonly",
                setTimeout: "readonly",
                clearInterval: "readonly",
                clearTimeout: "readonly",
                console: "readonly",
                Image: "readonly",
                getComputedStyle: "readonly",
                requestAnimationFrame: "readonly",
                URLSearchParams: "readonly",
                // Vendored libraries from static/lib/
                Vibrant: "readonly",
                FastAverageColor: "readonly",
            },
        },
        rules: {
            "no-undef": "error",
            "no-unused-vars": ["error", { args: "none", caughtErrors: "none" }],
            "no-redeclare": "error",
            "no-dupe-keys": "error",
            "no-dupe-args": "error",
            "no-duplicate-case": "error",
            "no-unreachable": "error",
            "no-constant-condition": "error",
            "no-cond-assign": "error",
            "no-func-assign": "error",
            "no-self-assign": "error",
            "no-sparse-arrays": "error",
            "use-isnan": "error",
            "valid-typeof": "error",
            "eqeqeq": ["warn", "smart"],
        },
    },
];
