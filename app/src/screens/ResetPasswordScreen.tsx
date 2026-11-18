import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  StatusBar,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export interface ResetPasswordScreenProps {
  onClose?: () => void;
  onSuccess?: () => void;
  initialExpired?: boolean;
}

export const ResetPasswordScreen: React.FC<ResetPasswordScreenProps> = ({
  onClose,
  onSuccess,
  initialExpired,
}) => {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ expired?: string; state?: string }>();

  // Determine if the link is expired/invalid
  const [isExpired, setIsExpired] = useState<boolean>(
    initialExpired ?? (params.expired === 'true' || params.state === 'expired')
  );

  // Form states
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isNewFocused, setIsNewFocused] = useState(false);
  const [isConfirmFocused, setIsConfirmFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Validation rules
  const hasMinLength = newPassword.length >= 8;
  const hasUppercase = /[A-Z]/.test(newPassword);
  const hasNumber = /[0-9]/.test(newPassword);
  const allRulesMet = hasMinLength && hasUppercase && hasNumber;
  const passwordsMatch = newPassword.length > 0 && newPassword === confirmPassword;
  const canSubmit = allRulesMet && passwordsMatch && !isLoading;

  const handleClose = () => {
    if (onClose) {
      onClose();
    } else {
      router.replace('/login');
    }
  };

  const handleBackToLogin = () => {
    router.replace('/login');
  };

  const handleRequestNewLink = () => {
    router.replace('/recuperar-contrasena');
  };

  const handleSavePassword = () => {
    if (!canSubmit) return;

    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      Alert.alert(
        '¡Contraseña actualizada!',
        'Tu contraseña ha sido cambiada con éxito. Ya puedes iniciar sesión en Zentheris.',
        [
          {
            text: 'Iniciar sesión',
            onPress: () => {
              if (onSuccess) {
                onSuccess();
              } else {
                router.replace('/login');
              }
            },
          },
        ]
      );
    }, 800);
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.container}
    >
      <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />

      {/* Top Header Bar */}
      <View style={[styles.headerBar, { paddingTop: Math.max(insets.top, 16) + 8 }]}>
        <TouchableOpacity
          style={styles.closeButton}
          onPress={handleClose}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          activeOpacity={0.7}
        >
          <Ionicons name="close-circle-outline" size={26} color="#C4D4CF" />
        </TouchableOpacity>
        <Text style={styles.headerBarTitle}>Nueva contraseña</Text>
        <View style={styles.headerSpacer} />
      </View>

      {/* Content depending on state */}
      {isExpired ? (
        /* ================= VISTA: ENLACE VENCIDO (Imagen 3) ================= */
        <View style={styles.expiredContainer}>
          <View style={styles.expiredCard}>
            <Ionicons
              name="close-circle"
              size={22}
              color="#EF4444"
              style={styles.expiredCardIcon}
            />
            <View style={styles.expiredCardTextContainer}>
              <Text style={styles.expiredCardTitle}>Este enlace ya no es válido</Text>
              <Text style={styles.expiredCardDescription}>
                Puede haber vencido o ya se usó. Solicita uno nuevo para cambiar tu contraseña.
              </Text>
            </View>
          </View>
        </View>
      ) : (
        /* ================= VISTA: CREAR CONTRASEÑA (Imagen 2) ================= */
        <ScrollView
          style={styles.formScrollView}
          contentContainerStyle={styles.formContent}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.headingTitle}>Crea una nueva contraseña</Text>
          <Text style={styles.headingSubtitle}>
            Úsala para iniciar sesión en Zentheris.
          </Text>

          {/* Input: Nueva contraseña */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Nueva contraseña</Text>
            <View
              style={[
                styles.inputWrapper,
                isNewFocused ? styles.inputWrapperActive : styles.inputWrapperNormal,
              ]}
            >
              <TextInput
                style={styles.textInput}
                placeholder="••••••••"
                placeholderTextColor="#5A7870"
                secureTextEntry={!showNewPassword}
                autoCapitalize="none"
                autoCorrect={false}
                value={newPassword}
                onChangeText={setNewPassword}
                onFocus={() => setIsNewFocused(true)}
                onBlur={() => setIsNewFocused(false)}
              />
              <TouchableOpacity
                onPress={() => setShowNewPassword((prev) => !prev)}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                activeOpacity={0.7}
                style={styles.eyeIconBtn}
              >
                <Ionicons
                  name={showNewPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={22}
                  color="#C4D4CF"
                />
              </TouchableOpacity>
            </View>
          </View>

          {/* Input: Confirmar contraseña */}
          <View style={[styles.fieldGroup, { marginTop: 18 }]}>
            <Text style={styles.fieldLabel}>Confirmar contraseña</Text>
            <View
              style={[
                styles.inputWrapper,
                isConfirmFocused ? styles.inputWrapperActive : styles.inputWrapperNormal,
              ]}
            >
              <TextInput
                style={styles.textInput}
                placeholder="••••••••"
                placeholderTextColor="#5A7870"
                secureTextEntry={!showConfirmPassword}
                autoCapitalize="none"
                autoCorrect={false}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                onFocus={() => setIsConfirmFocused(true)}
                onBlur={() => setIsConfirmFocused(false)}
              />
              <TouchableOpacity
                onPress={() => setShowConfirmPassword((prev) => !prev)}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                activeOpacity={0.7}
                style={styles.eyeIconBtn}
              >
                <Ionicons
                  name={showConfirmPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={22}
                  color="#C4D4CF"
                />
              </TouchableOpacity>
            </View>
          </View>

          {/* Checklist de Requisitos */}
          <View style={styles.checklistContainer}>
            <Text style={styles.checklistTitle}>Tu contraseña debe incluir:</Text>

            {/* Requisito: Mínimo 8 caracteres */}
            <View style={styles.checklistItem}>
              <Ionicons
                name="checkmark-circle-outline"
                size={20}
                color={hasMinLength ? '#5DD39E' : '#4E6E66'}
                style={styles.checkIcon}
              />
              <Text
                style={[
                  styles.checklistText,
                  hasMinLength && styles.checklistTextMet,
                ]}
              >
                Mínimo 8 caracteres
              </Text>
            </View>

            {/* Requisito: Una mayúscula */}
            <View style={styles.checklistItem}>
              <Ionicons
                name="checkmark-circle-outline"
                size={20}
                color={hasUppercase ? '#5DD39E' : '#4E6E66'}
                style={styles.checkIcon}
              />
              <Text
                style={[
                  styles.checklistText,
                  hasUppercase && styles.checklistTextMet,
                ]}
              >
                Una mayúscula
              </Text>
            </View>

            {/* Requisito: Un número */}
            <View style={styles.checklistItem}>
              <Ionicons
                name="checkmark-circle-outline"
                size={20}
                color={hasNumber ? '#5DD39E' : '#4E6E66'}
                style={styles.checkIcon}
              />
              <Text
                style={[
                  styles.checklistText,
                  hasNumber && styles.checklistTextMet,
                ]}
              >
                Un número
              </Text>
            </View>
          </View>
        </ScrollView>
      )}

      {/* Bottom Footer Actions */}
      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) + 16 }]}>
        {isExpired ? (
          /* Botones para enlace vencido */
          <>
            <TouchableOpacity
              style={styles.solidSubmitButton}
              onPress={handleRequestNewLink}
              activeOpacity={0.85}
            >
              <Text style={styles.solidSubmitButtonText}>Solicitar un nuevo enlace</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.linkButton}
              onPress={handleBackToLogin}
              activeOpacity={0.7}
            >
              <Text style={styles.linkButtonText}>Volver a iniciar sesión</Text>
            </TouchableOpacity>
          </>
        ) : (
          /* Botón para guardar contraseña */
          <TouchableOpacity
            style={[
              styles.guardarButton,
              canSubmit ? styles.guardarButtonActive : styles.guardarButtonDisabled,
            ]}
            onPress={handleSavePassword}
            disabled={!canSubmit}
            activeOpacity={canSubmit ? 0.85 : 1}
          >
            {isLoading ? (
              <ActivityIndicator color={canSubmit ? '#0D1F1A' : '#4E6E66'} />
            ) : (
              <Text
                style={[
                  styles.guardarButtonText,
                  canSubmit ? styles.guardarButtonTextActive : styles.guardarButtonTextDisabled,
                ]}
              >
                Guardar contraseña
              </Text>
            )}
          </TouchableOpacity>
        )}

        {/* Prototype Switcher Pill (Permite alternar entre ambas pantallas fácilmente) */}
        <TouchableOpacity
          style={styles.devToggle}
          onPress={() => setIsExpired((prev) => !prev)}
          activeOpacity={0.7}
        >
          <Text style={styles.devToggleText}>
            {isExpired
              ? '👁️ Ver pantalla: Crear contraseña'
              : '👁️ Ver pantalla: Enlace vencido'}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
};

export default ResetPasswordScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D1F1A',
    justifyContent: 'space-between',
  },
  headerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  closeButton: {
    width: 32,
    alignItems: 'flex-start',
    justifyContent: 'center',
  },
  headerBarTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: 20,
    fontWeight: '700',
    color: '#E8F1EE',
    letterSpacing: 0.2,
  },
  headerSpacer: {
    width: 32,
  },

  /* ================== Estilos de Formulario (Imagen 2) ================== */
  formScrollView: {
    flex: 1,
  },
  formContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
  },
  headingTitle: {
    fontSize: 26,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.2,
    marginBottom: 8,
  },
  headingSubtitle: {
    fontSize: 14.5,
    color: '#C4D4CF',
    lineHeight: 20,
    marginBottom: 24,
  },
  fieldGroup: {
    width: '100%',
  },
  fieldLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#FFFFFF',
    marginBottom: 8,
    letterSpacing: 0.1,
  },
  inputWrapper: {
    height: 52,
    borderRadius: 14,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
  },
  inputWrapperNormal: {
    backgroundColor: '#162B25',
    borderWidth: 1.5,
    borderColor: '#162B25',
  },
  inputWrapperActive: {
    backgroundColor: '#162B25',
    borderWidth: 1.5,
    borderColor: '#5DD39E',
  },
  textInput: {
    flex: 1,
    height: '100%',
    color: '#FFFFFF',
    fontSize: 16,
    letterSpacing: 1.5,
  },
  eyeIconBtn: {
    paddingLeft: 8,
    paddingVertical: 4,
  },

  /* Checklist de Requisitos */
  checklistContainer: {
    marginTop: 24,
  },
  checklistTitle: {
    fontSize: 14,
    color: '#C4D4CF',
    marginBottom: 14,
  },
  checklistItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  checkIcon: {
    marginRight: 10,
  },
  checklistText: {
    fontSize: 14.5,
    color: '#8CA59C',
  },
  checklistTextMet: {
    color: '#FFFFFF',
  },

  /* Botón Guardar */
  guardarButton: {
    height: 52,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  guardarButtonDisabled: {
    backgroundColor: '#142721',
    borderWidth: 1,
    borderColor: '#1A332B',
  },
  guardarButtonActive: {
    backgroundColor: '#5DD39E',
    shadowColor: '#5DD39E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  guardarButtonText: {
    fontSize: 15.5,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  guardarButtonTextDisabled: {
    color: '#4E6E66',
  },
  guardarButtonTextActive: {
    color: '#0D1F1A',
  },

  /* ================== Estilos de Enlace Vencido (Imagen 3) ================== */
  expiredContainer: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 16,
  },
  expiredCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#201517',
    borderWidth: 1.2,
    borderColor: '#4A2326',
    borderRadius: 14,
    padding: 16,
  },
  expiredCardIcon: {
    marginRight: 12,
    marginTop: 2,
  },
  expiredCardTextContainer: {
    flex: 1,
  },
  expiredCardTitle: {
    fontSize: 15.5,
    fontWeight: '700',
    color: '#F59099',
    marginBottom: 4,
    letterSpacing: 0.1,
  },
  expiredCardDescription: {
    fontSize: 13.5,
    color: '#C4D4CF',
    lineHeight: 19,
  },
  solidSubmitButton: {
    backgroundColor: '#5DD39E',
    height: 52,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 14,
    shadowColor: '#5DD39E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  solidSubmitButtonText: {
    color: '#0D1F1A',
    fontSize: 15.5,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  linkButton: {
    alignItems: 'center',
    paddingVertical: 8,
  },
  linkButtonText: {
    color: '#5DD39E',
    fontSize: 14.5,
    fontWeight: '600',
  },

  /* Footer común */
  footer: {
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  devToggle: {
    marginTop: 8,
    alignItems: 'center',
    paddingVertical: 6,
  },
  devToggleText: {
    color: '#5A7870',
    fontSize: 11.5,
    fontWeight: '500',
  },
});

