// Shared GSAP easings. Blueprint rule (\u00a76): never instantly switch states.
// Centralizing easings keeps timing language consistent across all modules.
export const EASE = {
    // Cinematic: slow start, snappy middle, gentle settle. Use for scene
    // transitions and major dock/undock moves.
    cinematic: "power3.inOut",
    // Sharp emphasis on the way out. Good for "popping" hologram panels in.
    pop: "back.out(1.6)",
    // Asymmetric: quick out, slow in. Use for things that need to feel
    // "intentional" but not snappy (orb settling into dock).
    settle: "power4.out",
    // Linear UI fades (opacity-only). Don't use for movement.
    fade: "sine.inOut",
    // Tiny-amplitude breath / idle motion.
    breath: "sine.inOut",
};
// Standard durations (seconds). Keep these in lockstep so two timelines
// starting at the same moment land together.
export const DUR = {
    micro: 0.18, // dock button press, hover
    short: 0.4, // notification slide
    base: 0.7, // panel open, caption fade
    scene: 0.9, // big scene swap
    long: 1.4, // map zoom-in choreography
};
