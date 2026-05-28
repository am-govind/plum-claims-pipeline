// Dev-mode gate for review-only surfaces (the eval page, the
// "Simulate component failure" toggle on the claim form).
//
// Default is ON so the Plum reviewer can clone, run, and demo
// without setting any env var. For a customer-facing production
// build, set NEXT_PUBLIC_DEV_MODE=false at build time and the
// review surfaces disappear from the navigation, the home page,
// the eval route, and the submit form.
export const IS_DEV_MODE: boolean =
  process.env.NEXT_PUBLIC_DEV_MODE !== "false";
