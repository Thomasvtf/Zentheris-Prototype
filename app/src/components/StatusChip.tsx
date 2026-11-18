import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { estadoColor, estadoIcon, EstadoType } from '../utils/statusHelpers';

export interface StatusChipProps {
  title: string;
  subtitle?: string;
  estado?: EstadoType;
  iconName?: keyof typeof Ionicons.glyphMap;
  iconColor?: string;
  iconSize?: number;
  style?: ViewStyle;
}

export const StatusChip: React.FC<StatusChipProps> = ({
  title,
  subtitle,
  estado = 'Normal',
  iconName,
  iconColor,
  iconSize = 16,
  style,
}) => {
  const resolvedColor = iconColor || estadoColor(estado);
  const resolvedIcon = iconName || (estadoIcon(estado) as keyof typeof Ionicons.glyphMap);

  return (
    <View style={[styles.container, style]}>
      <Ionicons name={resolvedIcon} size={iconSize} color={resolvedColor} style={styles.icon} />
      <View style={styles.content}>
        <Text style={[styles.title, { color: resolvedColor }]}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#081712',
    borderWidth: 1,
    borderColor: '#163629',
    borderRadius: 10,
    padding: 10,
    marginTop: 14,
    gap: 8,
  },
  icon: {
    marginTop: 2,
  },
  content: {
    flex: 1,
  },
  title: {
    fontSize: 12,
    fontWeight: '600',
    lineHeight: 16,
  },
  subtitle: {
    color: '#718096',
    fontSize: 11,
    marginTop: 2,
    lineHeight: 15,
  },
});

