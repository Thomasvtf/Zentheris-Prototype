import React from 'react';
import { View, Text, StyleSheet, ViewStyle, TextStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { estadoColor, estadoBadgeBg, estadoBorderColor, estadoIcon, EstadoType } from '../utils/statusHelpers';

export interface StatusBadgeProps {
  estado?: EstadoType;
  showIcon?: boolean;
  iconName?: keyof typeof Ionicons.glyphMap;
  label?: string;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  estado = 'Normal',
  showIcon = false,
  iconName,
  label,
  style,
  textStyle,
}) => {
  const color = estadoColor(estado);
  const bgColor = estadoBadgeBg(estado);
  const borderColor = estadoBorderColor(estado);
  const icon = iconName || (estadoIcon(estado) as keyof typeof Ionicons.glyphMap);
  const text = label || estado;

  return (
    <View
      style={[
        styles.badge,
        { backgroundColor: bgColor, borderColor },
        style,
      ]}
    >
      {showIcon && (
        <Ionicons
          name={icon}
          size={12}
          color={color}
          style={{ marginRight: 4 }}
        />
      )}
      <Text style={[styles.badgeText, { color }, textStyle]}>
        {text}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 14,
    borderWidth: 1,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
});

