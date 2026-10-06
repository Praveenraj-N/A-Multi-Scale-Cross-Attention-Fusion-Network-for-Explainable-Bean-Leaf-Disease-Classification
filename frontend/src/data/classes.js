// Class order matches the model's output indices (ImageFolder order used in training).
export const CLASSES = [
  {
    id: "angular_leaf_spot",
    index: 0,
    label: "Angular leaf spot",
    color: "var(--color-cls-als)",
    pathogen: "Fungal disease (Pseudocercospora griseola)",
    signs: "Small, angular brown lesions bounded by the leaf veins, often with yellowing around them."
  },
  {
    id: "bean_rust",
    index: 1,
    label: "Bean rust",
    color: "var(--color-cls-rust)",
    pathogen: "Fungal disease (Uromyces appendiculatus)",
    signs: "Small reddish-brown pustules scattered across the leaf surface, sometimes with a pale halo."
  },
  {
    id: "healthy",
    index: 2,
    label: "Healthy",
    color: "var(--color-cls-healthy)",
    pathogen: "No disease",
    signs: "Uniform green leaf tissue without lesions or pustules."
  }
];

export const CLASS_BY_ID = Object.fromEntries(CLASSES.map((c) => [c.id, c]));

export function classLabel(id) {
  return CLASS_BY_ID[id]?.label ?? id;
}

export function classColor(id) {
  return CLASS_BY_ID[id]?.color ?? "var(--color-ink-3)";
}
