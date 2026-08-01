/// <reference types="vite/client" />
/// <reference types="@react-three/fiber" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_SNAPSHOT_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
