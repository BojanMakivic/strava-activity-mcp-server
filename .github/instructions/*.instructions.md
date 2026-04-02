pr-review.instructions.md — Copilot PR Code Review Guidelines
Objective

Enhance code quality, readability, and maintainability by performing structured and consistent pull request (PR) reviews.

Core Principles
Be precise and actionable – Avoid vague comments; suggest concrete improvements.
Prioritize impact – Focus on correctness, security, and performance before style.
Be concise – Keep feedback short but meaningful.
Respect context – Align suggestions with the existing codebase and architecture.

Review Checklist

1. Correctness
Identify logical errors, edge cases, and potential bugs. Verify that the implementation matches the intended behavior. Ensure proper error handling and input validation.
2. Readability & Maintainability
Suggest clearer variable/function names where needed. Recommend simplifications for complex logic. Ensure consistent formatting and structure.
3. Performance
Highlight inefficient algorithms or unnecessary computations. Suggest optimizations only when they provide meaningful benefit. Avoid premature optimization.
4. Security
Detect potential vulnerabilities (e.g., injection, unsafe deserialization). Ensure sensitive data is handled securely. Check authentication and authorization logic if applicable.
5. Best Practices
Follow language-specific conventions and idioms. Encourage modular, reusable code. Flag duplicated logic.
6. Testing
Check if relevant tests are included or updated. Suggest edge case tests where missing. Ensure test clarity and coverage.

Commenting Style
Use clear, direct language. Prefer suggestions over criticism. Provide improved code snippets when helpful.

Example:

Consider simplifying this loop using a list comprehension:
result = [x for x in items if x.is_valid()]

When to Comment vs Approve
Comment when:
There are bugs, risks, or unclear logic. Improvements significantly enhance quality.
Approve when:
Code is correct, readable, and aligned with standards. Only minor or subjective improvements remain.
Avoid
Overly verbose explanations. Nitpicking trivial style issues unless consistent. Rewriting code without clear benefit.
Goal
Deliver high-signal, low-noise feedback that helps developers ship reliable, clean, and maintainable code efficiently.
