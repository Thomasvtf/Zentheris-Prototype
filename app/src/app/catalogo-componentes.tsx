/** Ruta interna: catálogo de componentes. Solo existe en desarrollo (__DEV__); fuera, redirige. */
import { Redirect } from 'expo-router';

import { ComponentCatalogScreen } from '@/screens/ComponentCatalog/ComponentCatalogScreen';

export default function CatalogoComponentes() {
  if (!__DEV__) return <Redirect href="/" />;
  return <ComponentCatalogScreen />;
}
