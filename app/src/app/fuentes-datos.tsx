import React from 'react';
import { MOCK_HOGAR_ID } from '../api/devMocks';
import { FuentesDatosScreen } from '../screens/FuentesDatosScreen';

export default function Page() {
  // TODO(pendiente: hogarId): vendrá del estado de sesión/hogar; MOCK_HOGAR_ID es null fuera del modo de ejemplo.
  return <FuentesDatosScreen hogarId={MOCK_HOGAR_ID} />;
}
