/**
 * Filmic grain + scanline overlay. Opacity is driven by the active theme's
 * --zen-grain CSS variable, so each theme gets a different amount of texture.
 * Purely decorative: pointer-events:none, aria-hidden.
 */
export default function Atmosphere() {
  return <div className="zen-atmosphere" aria-hidden data-testid="atmosphere" />;
}
