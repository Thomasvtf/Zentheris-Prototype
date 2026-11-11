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
  onClose?: () => void;
  onBackToLogin?: () => void;
}

export const VerifyEmailScreen: React.FC<VerifyEmailScreenProps> = ({
  email: propEmail,
  onClose,
  onBackToLogin,
}) => {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ email?: string }>();
  const email = propEmail || params.email || 'ana@correo.com';

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
        `Hemos reenviado el enlace de confirmación a ${email}.`
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
          <Ionicons name="close-circle-outline" size={26} color="#8CA59C" />
        </TouchableOpacity>
        <Text style={styles.headerBarTitle}>Revisa tu correo</Text>
      </View>

      {/* Center Content */}
      <View style={styles.content}>
        {/* Circular Mail Icon Badge */}
        <View style={styles.mailIconBadge}>
          <Ionicons name="mail-outline" size={38} color="#5DD39E" />
        </View>

        <Text style={styles.title}>Revisa tu correo</Text>

        <Text style={styles.description}>
          Enviamos un enlace a <Text style={styles.emailHighlight}>{email}</Text> para confirmar tu cuenta. Ábrelo desde este teléfono para continuar.
        </Text>

        <Text style={styles.spamNote}>
          ¿No llegó? Revisa la carpeta de spam o reenvíalo.
        </Text>
      </View>

      {/* Bottom Actions */}
      <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, 16) + 12 }]}>
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
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  closeButton: {
    paddingRight: 10,
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
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
    marginTop: -40,
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
    fontSize: 14,
    color: '#A6BBB4',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 20,
  },
  emailHighlight: {
    color: '#E8F1EE',
    fontWeight: '500',
  },
  spamNote: {
    fontSize: 13,
    color: '#8CA59C',
    textAlign: 'center',
    lineHeight: 18,
  },
  footer: {
    paddingHorizontal: 22,
    paddingTop: 12,
  },
  outlinedButton: {
    height: 50,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#5DD39E',
    backgroundColor: 'transparent',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  outlinedButtonText: {
    color: '#5DD39E',
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

