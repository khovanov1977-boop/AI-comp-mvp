export function MediaPanel() {
  return (
    <aside className="panel stack">
      <h2>Mock media</h2>
      <p className="muted">Image, video, and voice providers are placeholders in Sprint 0.</p>
      <img
        alt="Mock character placeholder"
        src="https://placehold.co/600x600/png?text=Mock+Image"
        style={{ width: "100%", borderRadius: 8, border: "1px solid var(--line)" }}
      />
    </aside>
  );
}
