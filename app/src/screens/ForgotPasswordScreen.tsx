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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export interface ForgotPasswordScreenProps {
  onBack?: () => void;
  onSuccess?: (email: string) => void;
}

export const ForgotPasswordScreen: React.FC<ForgotPasswordScreenProps> = ({
  onBack,
  onSuccess,
}) => {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      router.back();
    }
  };

  const handleSendLink = () => {
    if (!email.trim()) {
      Alert.alert('Correo requerido', 'Por favor ingresa tu correo electrónico.');
      return;
    }

    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      if (onSuccess) {
        onSuccess(email);
      } else {
        router.push({
          pathname: '/revisa-tu-correo',
          params: { email: email.trim() },
        });
      }
    }, 600);
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
          style={styles.backButton}
          onPress={handleBack}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          activeOpacity={0.7}
        >
          <Ionicons name="chevron-back" size={24} color="#C4D4CF" />
        </TouchableOpacity>
        <Text style={styles.headerBarTitle}>Recuperar contraseña</Text>
      </View>

      {/* Main Content */}
      <View style={styles.content}>
        <Text style={styles.mainTitle}>¿Olvidaste tu contraseña?</Text>
        <Text style={styles.subtitle}>
          Escribe el correo de tu cuenta y te enviaremos un enlace para crear una nueva.
        </Text>

        {/* Email Field */}
        <View style={styles.inputGroup}>
          <Text style={styles.inputLabel}>Correo electrónico</Text>
          <View style={[styles.inputContainer, isFocused && styles.inputContainerFocused]}>
            <TextInput
              style={styles.textInput}
              placeholder="ana@correo.com"
              placeholderTextColor="#5A776D"
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              value={email}
              onChangeText={setEmail}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
            />
          </View>
          <Text style={styles.helperText}>
            Si el correo está registrado, recibirás el enlace en unos minutos.
          </Text>
        </View>
      </View>

      {/* Bottom Actions */}
      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) + 12 }]}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={handleSendLink}
          disabled={isLoading}
          activeOpacity={0.85}
        >
          {isLoading ? (
            <ActivityIndicator color="#0D1F1A" />
          ) : (
            <Text style={styles.primaryButtonText}>Enviar enlace</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.backToLoginButton}
          onPress={handleBack}
          activeOpacity={0.7}
        >
          <Text style={styles.backToLoginText}>Volver a iniciar sesión</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
};

export default ForgotPasswordScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D1F1A',
    justifyContent: 'space-between',
  },
  headerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  backButton: {
    paddingRight: 8,
    paddingVertical: 4,
  },
  headerBarTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#C4D4CF',
    letterSpacing: 0.2,
  },
  content: {
    flex: 1,
    paddingHorizontal: 22,
    paddingTop: 24,
  },
  mainTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 8,
    letterSpacing: 0.2,
  },
  subtitle: {
    fontSize: 14,
    color: '#8CA59C',
    lineHeight: 20,
    marginBottom: 28,
  },
  inputGroup: {
    width: '100%',
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '500',
    color: '#E8F1EE',
    marginBottom: 8,
  },
  inputContainer: {
    backgroundColor: '#1A312A',
    borderRadius: 12,
    borderWidth: 1.2,
    borderColor: '#1A312A',
    paddingHorizontal: 14,
    height: 50,
    justifyContent: 'center',
  },
  inputContainerFocused: {
    borderColor: '#5DD39E',
  },
  textInput: {
    color: '#FFFFFF',
    fontSize: 15,
    height: '100%',
  },
  helperText: {
    fontSize: 13,
    color: '#8CA59C',
    lineHeight: 18,
    marginTop: 10,
  },
  footer: {
    paddingHorizontal: 22,
    paddingTop: 12,
  },
  primaryButton: {
    backgroundColor: '#5DD39E',
    height: 50,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#5DD39E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
    marginBottom: 16,
  },
  primaryButtonText: {
    color: '#0D1F1A',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  backToLoginButton: {
    alignItems: 'center',
    paddingVertical: 6,
  },
  backToLoginText: {
    color: '#5DD39E',
    fontSize: 14,
    fontWeight: '600',
  },
});

