export function authDestination() {
  const slug = new URLSearchParams(window.location.search).get("example");
  return slug && /^[a-z0-9-]+$/.test(slug) ? `/examples#${slug}` : "/characters";
}
