# Gallery

This gallery is generated from the example scripts shipped with `cleanfig`.

Each panel below uses the current SVG output from `examples/output/`, copied into `docs/gallery/assets/` for GitHub Pages hosting.

## Available Examples

<style>
.cf-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
  margin-top: 1.5rem;
}
.cf-card {
  border: 1px solid #d7dde5;
  border-radius: 12px;
  padding: 1rem;
  background: #ffffff;
  box-shadow: 0 4px 18px rgba(22, 28, 36, 0.05);
}
.cf-card h2 {
  margin-top: 0;
  margin-bottom: 0.35rem;
  font-size: 1.05rem;
}
.cf-card p {
  margin-top: 0.35rem;
  margin-bottom: 0.75rem;
  line-height: 1.45;
}
.cf-card img {
  width: 100%;
  height: auto;
  border-radius: 8px;
  background: #f6f8fa;
}
.cf-meta {
  font-size: 0.92rem;
  color: #4f5b67;
}
.cf-links {
  margin-top: 0.75rem;
  font-size: 0.95rem;
}
</style>

<div class="cf-gallery">
  <div class="cf-card">
    <h2>basic_line</h2>
    <p>Minimal line + scatter example with math labels, legend entries, and publication-style defaults.</p>
    <div class="cf-meta">Script: <code>examples/basic_line.py</code></div>
    <img src="assets/basic_line.svg" alt="basic_line example">
    <div class="cf-links">
      <a href="assets/basic_line.svg">SVG</a>
    </div>
  </div>

  <div class="cf-card">
    <h2>esec_dual_y_light</h2>
    <p>Dual-Y geophysical example from a bundled ESEC catalog extract, using log scaling, error bars, and a pandas-loaded dataframe.</p>
    <div class="cf-meta">Script: <code>examples/esec_dual_y_light.py</code></div>
    <img src="assets/esec_dual_y_light.svg" alt="esec_dual_y_light example">
    <div class="cf-links">
      <a href="assets/esec_dual_y_light.svg">SVG</a>
    </div>
  </div>

  <div class="cf-card">
    <h2>four_panels_figure</h2>
    <p>Default publication-theme four-panel scientific composition combining scatter, regression, bar, field, and colorbar layout.</p>
   

  <div class="cf-card">
    <h2>four_panels_light</h2>
    <p>Publication-theme wrapper for the four-panel figure, suitable for README and paper-oriented examples.</p>
    <div class="cf-meta">Script: <code>examples/four_panels_light.py</code></div>
    <img src="assets/four_panels_light.svg" alt="four_panels_light example">
    <div class="cf-links">
      <a href="assets/four_panels_light.svg">SVG</a>
    </div>
  </div>

  <div class="cf-card">
    <h2>four_panels_dark</h2>
    <p>Dark presentation variant of the four-panel figure, demonstrating the optional theme switch without API changes.</p>
    <div class="cf-meta">Script: <code>examples/four_panels_dark.py</code></div>
    <img src="assets/four_panels_dark.svg" alt="four_panels_dark example">
    <div class="cf-links">
      <a href="assets/four_panels_dark.svg">SVG</a>
    </div>
  </div>


  <div class="cf-card">
    <h2>violin_box_light</h2>
    <p>Explicit publication-theme wrapper for the violin and box gallery example.</p>
    <div class="cf-meta">Script: <code>examples/violin_box_light.py</code></div>
    <img src="assets/violin_box_light.svg" alt="violin_box_light example">
    <div class="cf-links">
      <a href="assets/violin_box_light.svg">SVG</a>
    </div>
  </div>


</div>

## Notes

- The ESEC example expects `pandas` and the bundled file `examples/Data/IRIS_DMC_esecEventsDb.txt`.
- PDF export requires the Rust backend.
- The gallery is intentionally SVG-first for crisp GitHub Pages rendering.
