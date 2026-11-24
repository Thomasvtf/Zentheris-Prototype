/**
 * ConfirmDialog (ConfirmDialog.md; Figma `Dialogo/Confirmacion` A10 y A11): pregunta, consecuencia,
 * botón principal arriba y «Cancelar» abajo, a todo el ancho y en el mismo orden en Android e iOS.
 * Se muestra mientras está montado: la pantalla lo pinta solo cuando hay algo que confirmar.
 * Extensión de la app: `ocupado` bloquea los dos botones mientras la acción corre.
 */
import React from 'react';
import { Modal, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, textStyle } from '@/theme';

import { Button } from './Button';

export interface ConfirmDialogProps {
  titulo: string;
  descripcion?: string;
  tono?: 'destructivo' | 'normal';
  confirmar?: string;
  cancelar?: string;
  onConfirmar?: () => void;
  onCancelar?: () => void;
  ocupado?: boolean;
}

export function ConfirmDialog({ titulo, descripcion, tono = 'normal', confirmar, cancelar, onConfirmar, onCancelar, ocupado = false }: ConfirmDialogProps) {
  return (
    <Modal visible transparent animationType="fade" onRequestClose={ocupado ? undefined : onCancelar}>
      <View style={styles.overlay}>
        <View style={styles.card} accessibilityViewIsModal>
          <Text style={styles.title} accessibilityRole="header">
            {titulo}
          </Text>
          {descripcion ? <Text style={styles.body}>{descripcion}</Text> : null}
          <View style={styles.actions}>
            {confirmar ? (
              <Button variante={tono === 'destructivo' ? 'destructivo' : 'primario'} estado={ocupado ? 'cargando' : 'normal'} bloque onClick={onConfirmar}>
                {confirmar}
              </Button>
            ) : null}
            {cancelar ? (
              <Button variante="secundario" estado={ocupado ? 'deshabilitado' : 'normal'} bloque onClick={onCancelar}>
                {cancelar}
              </Button>
            ) : null}
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: colors['background-overlay'], justifyContent: 'center', paddingHorizontal: spacing['24'] },
  card: {
    backgroundColor: colors['background-surfaceAlt'],
    borderColor: colors['border-subtle'],
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing['24'],
    gap: spacing['12'],
  },
  title: { ...textStyle('display-m'), color: colors['text-primary'] },
  body: { ...textStyle('body-s-regular'), color: colors['text-muted'] },
  actions: { gap: spacing['12'], marginTop: spacing['8'] },
});
