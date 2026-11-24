import React from 'react';
import { MOCK_HOGAR_ID } from '../api/devMocks';
import { MiembrosHogarScreen } from '../screens/MiembrosHogarScreen';

export default function Page() {
  // TODO(pendiente: hogarId): vendrá del estado de sesión/hogar; MOCK_HOGAR_ID es null fuera del modo de ejemplo.
  return <MiembrosHogarScreen hogarId={MOCK_HOGAR_ID} />;
}
