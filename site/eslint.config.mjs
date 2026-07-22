import next from "eslint-config-next";

// Next 16 memuat flat config native — pakai langsung, tanpa FlatCompat.
const eslintConfig = [
  ...next,
  { ignores: [".next/**", "out/**", "node_modules/**"] },
];

export default eslintConfig;
