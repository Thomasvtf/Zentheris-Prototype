import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  StatusBar,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export interface VerifyEmailScreenProps {
  email?: string;
  mode?: 'recovery' | 'verify';
  onClose?: () => void;
  onBackToLogin?: () => void;
}

export const VerifyEmailScreen: React.FC<VerifyEmailScreenProps> = ({
  email: propEmail,
  mode: propMode,
  onClose,
  onBackToLogin,
}) => {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ email?: string; mode?: 'recovery' | 'verify' }>();
  const email = propEmail || params.email || 'ana@correo.com';
  const mode = propMode || params.mode || 'recovery';

  const [isResending, setIsResending] = useState(false);

  const handleClose = () => {
    if (onClose) {
      onClose();
    } else {
      router.replace('/login');
    }
  };

  const handleBackToLogin = () => {
    if (onBackToLogin) {
      onBackToLogin();
    } else {
      router.replace('/login');
    }
  };

  const handleResend = () => {
    setIsResending(true);
    setTimeout(() => {
      setIsResending(false);
      Alert.alert(
        'Enlace reenviado',
        `Hemos reenviado el enlace a ${email}.`,
        [
          { text: 'Aceptar', style: 'cancel' },
          {
            text: 'Abrir enlace (Nueva contraseña)',
            onPress: () => router.push({ pathname: '/nueva-contrasena', params: { email } }),
          },
        ]
      );
    }, 700);
  };

  return (
    <View style={styles.container}>
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
        <Text style={styles.headerBarTitle}>Revisa tu correo</Text>
        <View style={styles.headerSpacer} />
      </View>

      {/* Center Content */}
      <View style={styles.content}>
        {/* Circular Mail Icon Badge */}
        <View style={styles.mailIconBadge}>
          <Ionicons name="mail-outline" size={38} color="#5DD39E" />
        </View>

        <Text style={styles.title}>Revisa tu correo</Text>

        {mode === 'recovery' ? (
          <Text style={styles.description}>
            Si <Text style={styles.emailHighlight}>{email}</Text> está registrado, recibirás un enlace para crear una nueva contraseña.
          </Text>
        ) : (
          <Text style={styles.description}>
            Enviamos un enlace a <Text style={styles.emailHighlight}>{email}</Text> para confirmar tu cuenta. Ábrelo desde este teléfono para continuar.
          </Text>
        )}

        <Text style={styles.spamNote}>
          ¿No llegó? Revisa la carpeta de spam o reenvíalo.
        </Text>
      </View>

      {/* Bottom Actions */}
      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) + 16 }]}>
        <TouchableOpacity
          style={styles.outlinedButton}
          onPress={handleResend}
          disabled={isResending}
          activeOpacity={0.8}
        >
          {isResending ? (
            <ActivityIndicator color="#5DD39E" />
          ) : (
            <Text style={styles.outlinedButtonText}>Reenviar enlace</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.backToLoginButton}
          onPress={handleBackToLogin}
          activeOpacity={0.7}
        >
          <Text style={styles.backToLoginText}>Volver a iniciar sesión</Text>
        </TouchableOpacity>

        {/* Prototype testing shortcut */}
        <TouchableOpacity
          style={styles.prototypeLink}
          onPress={() => router.push({ pathname: '/nueva-contrasena', params: { email } })}
          activeOpacity={0.7}
        >
          <Text style={styles.prototypeLinkText}>⚡ Probar pantalla: Nueva contraseña</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.prototypeLink, { marginTop: 2 }]}
          onPress={() => router.push('/onboarding')}
          activeOpacity={0.7}
        >
          <Text style={styles.prototypeLinkText}>⚡ Probar pantalla: Onboarding (Crea tu hogar)</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

export default VerifyEmailScreen;

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
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 28,
    marginTop: -30,
  },
  mailIconBadge: {
    width: 82,
    height: 82,
    borderRadius: 41,
    backgroundColor: '#163B30',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 16,
    textAlign: 'center',
    letterSpacing: 0.2,
  },
  description: {
    fontSize: 14.5,
    color: '#C4D4CF',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 20,
    maxWidth: 320,
  },
  emailHighlight: {
    color: '#FFFFFF',
    fontWeight: '500',
  },
  spamNote: {
    fontSize: 13.5,
    color: '#8CA59C',
    textAlign: 'center',
    lineHeight: 19,
  },
  footer: {
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  outlinedButton: {
    height: 52,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: '#5DD39E',
    backgroundColor: 'transparent',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 14,
  },
  outlinedButtonText: {
    color: '#5DD39E',
    fontSize: 15.5,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  backToLoginButton: {
    alignItems: 'center',
    paddingVertical: 8,
  },
  backToLoginText: {
    color: '#5DD39E',
    fontSize: 14.5,
    fontWeight: '600',
  },
  prototypeLink: {
    marginTop: 8,
    alignItems: 'center',
    paddingVertical: 6,
  },
  prototypeLinkText: {
    color: '#5A7870',
    fontSize: 11.5,
    fontWeight: '500',
  },
});
