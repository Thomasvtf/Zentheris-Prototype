import React from 'react';
import { MOCK_HOGAR_ID } from '../api/devMocks';
import { EstablecerMetaScreen } from '../screens/EstablecerMetaScreen';

export default function Page() {
  // TODO(pendiente: hogarId): vendrá del estado de sesión/hogar; MOCK_HOGAR_ID es null fuera del modo de ejemplo.
  return <EstablecerMetaScreen hogarId={MOCK_HOGAR_ID} />;
}
