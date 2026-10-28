import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Image,
  Dimensions,
  Animated,
  PanResponder,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
  Alert,
  StatusBar,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

// Screen dimensions
const { height: SCREEN_HEIGHT } = Dimensions.get('window');

export interface AuthScreenProps {
  initialTab?: 'login' | 'register';
  initialOpen?: boolean;
  onSuccess?: () => void;
}

export const LoginScreen: React.FC<AuthScreenProps> = ({
  initialTab = 'login',
  initialOpen = false,
  onSuccess,
}) => {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  // Dynamic drawer sizing based on screen and safe area
  const bottomInset = insets.bottom || 12;
  const CLOSED_DRAWER_HEIGHT = 88 + bottomInset;
  const OPEN_DRAWER_HEIGHT = Math.min(SCREEN_HEIGHT * 0.84, 660);
  const MAX_TRANSLATE_Y = OPEN_DRAWER_HEIGHT - CLOSED_DRAWER_HEIGHT;

  // Active form tab ('login' | 'register')
  const [activeTab, setActiveTab] = useState<'login' | 'register'>(initialTab);
  const [isOpen, setIsOpen] = useState<boolean>(initialOpen);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Form states - Login
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Form states - Register
  const [registerName, setRegisterName] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [showRegisterConfirmPassword, setShowRegisterConfirmPassword] = useState(false);

  // Focus states for input styling
  const [focusedInput, setFocusedInput] = useState<string | null>(null);

  // Animation values
  // 0 = fully opened, MAX_TRANSLATE_Y = closed (only tabs visible at bottom)
  const translateY = useRef(new Animated.Value(initialOpen ? 0 : MAX_TRANSLATE_Y)).current;
  const currentTranslateY = useRef(initialOpen ? 0 : MAX_TRANSLATE_Y);

  // Keep track of current translation for gesture delta calculations
  useEffect(() => {
    const listenerId = translateY.addListener((val) => {
      currentTranslateY.current = val.value;
    });
    return () => {
      translateY.removeListener(listenerId);
    };
  }, [translateY]);

  // Open drawer function
  const openDrawer = (targetTab?: 'login' | 'register') => {
    if (targetTab) {
      setActiveTab(targetTab);
    }
    setIsOpen(true);
    Animated.spring(translateY, {
      toValue: 0,
      damping: 24,
      mass: 0.9,
      stiffness: 180,
      useNativeDriver: true,
    }).start();
  };

  // Close drawer function
  const closeDrawer = () => {
    setIsOpen(false);
    Animated.spring(translateY, {
      toValue: MAX_TRANSLATE_Y,
      damping: 24,
      mass: 0.9,
      stiffness: 180,
      useNativeDriver: true,
    }).start();
  };

  // PanResponder for drag up / drag down gestures
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,
      onMoveShouldSetPanResponder: (_, gestureState) => {
        // Trigger pan if vertical swipe exceeds small movement
        return Math.abs(gestureState.dy) > 7 && Math.abs(gestureState.dy) > Math.abs(gestureState.dx);
      },
      onPanResponderGrant: () => {
        translateY.extractOffset();
      },
      onPanResponderMove: (_, gestureState) => {
        // Only allow dragging within bounds [0, MAX_TRANSLATE_Y]
        const nextVal = currentTranslateY.current + gestureState.dy;
        if (nextVal >= 0 && nextVal <= MAX_TRANSLATE_Y) {
          translateY.setValue(gestureState.dy);
        }
      },
      onPanResponderRelease: (_, gestureState) => {
        translateY.flattenOffset();
        const movedY = currentTranslateY.current;

        // Quick flick up: open
        if (gestureState.vy < -0.3) {
          openDrawer();
          return;
        }

        // Quick flick down: close
        if (gestureState.vy > 0.3) {
          closeDrawer();
          return;
        }

        // Snap depending on position threshold (50% of travel)
        if (movedY < MAX_TRANSLATE_Y * 0.5) {
          openDrawer();
        } else {
          closeDrawer();
        }
      },
      onPanResponderTerminate: () => {
        translateY.flattenOffset();
        if (currentTranslateY.current < MAX_TRANSLATE_Y * 0.5) {
          openDrawer();
        } else {
          closeDrawer();
        }
      },
    })
  ).current;

  // Handle Tab buttons click
  const handleTabPress = (tab: 'login' | 'register') => {
    setActiveTab(tab);
    if (!isOpen) {
      openDrawer(tab);
    }
  };

  // Handle Login submission
  const handleLoginSubmit = () => {
    if (!loginEmail.trim() || !loginPassword.trim()) {
      Alert.alert('Campos requeridos', 'Por favor ingresa tu correo y contraseña.');
      return;
    }

    setIsLoading(true);
    // Simulate login or call API/Supabase
    setTimeout(() => {
      setIsLoading(false);
      if (onSuccess) {
        onSuccess();
      } else {
        try {
          router.replace('/panel');
        } catch {
          router.replace('/');
        }
      }
    }, 800);
  };

  // Handle Register submission
  const handleRegisterSubmit = () => {
    if (!registerName.trim() || !registerEmail.trim() || !registerPassword.trim()) {
      Alert.alert('Campos requeridos', 'Por favor completa todos los campos requeridos.');
      return;
    }
    if (registerPassword !== registerConfirmPassword) {
      Alert.alert('Error', 'Las contraseñas no coinciden.');
      return;
    }

    setIsLoading(true);
    // Simulate register or call API/Supabase
    setTimeout(() => {
      setIsLoading(false);
      Alert.alert('Cuenta creada', 'Tu cuenta ha sido creada exitosamente. ¡Bienvenido a Zentheris!', [
        {
          text: 'Continuar',
          onPress: () => {
            if (onSuccess) {
              onSuccess();
            } else {
              try {
                router.replace('/panel');
              } catch {
                setActiveTab('login');
              }
            }
          },
        },
      ]);
    }, 800);
  };

  // Interpolation for dim backdrop overlay
  const backdropOpacity = translateY.interpolate({
    inputRange: [0, MAX_TRANSLATE_Y],
    outputRange: [0.65, 0],
    extrapolate: 'clamp',
  });

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0D1F1A" />

      {/* Main Screen Branding */}
      <View style={[styles.brandingContainer, { paddingBottom: CLOSED_DRAWER_HEIGHT }]}>
        <View style={styles.logoWrapper}>
          <Image
            source={require('../../assets/images/zentheris-logo.png')}
            style={styles.logoImage}
            resizeMode="contain"
          />
        </View>
        <Text style={styles.brandTitle}>Zentheris</Text>
      </View>

      {/* Backdrop overlay when drawer is open */}
      <Animated.View
        pointerEvents={isOpen ? 'auto' : 'none'}
        style={[
          styles.backdrop,
          {
            opacity: backdropOpacity,
          },
        ]}
      >
        <TouchableOpacity
          style={StyleSheet.absoluteFill}
          activeOpacity={1}
          onPress={closeDrawer}
        />
      </Animated.View>

      {/* Sliding Drawer (Cajón) */}
      <Animated.View
        style={[
          styles.drawerContainer,
          {
            height: OPEN_DRAWER_HEIGHT,
            transform: [{ translateY }],
          },
        ]}
      >
        {/* Gesture Responder Area (Header + Drag Handle) */}
        <View {...panResponder.panHandlers} style={styles.drawerHeaderArea}>
          {/* Dual Tab bar in the header with separate pill shapes */}
          <View style={styles.dockTabsRow}>
            {/* Left Tab: Iniciar sesión */}
            <TouchableOpacity
              style={[
                styles.tabDockButton,
                styles.tabDockButtonLeft,
                activeTab === 'login' && styles.tabDockButtonActive,
              ]}
              onPress={() => handleTabPress('login')}
              activeOpacity={0.85}
            >
              <Text
                style={[
                  styles.tabDockText,
                  activeTab === 'login' && styles.tabDockTextActive,
                ]}
              >
                Iniciar sesión
              </Text>
              {isOpen && activeTab === 'login' && <View style={styles.activeTabIndicator} />}
            </TouchableOpacity>

            {/* Gap / Notch Divider between the two tabs */}
            <View style={styles.tabDividerNotch} />

            {/* Right Tab: Registro */}
            <TouchableOpacity
              style={[
                styles.tabDockButton,
                styles.tabDockButtonRight,
                activeTab === 'register' && styles.tabDockButtonActive,
              ]}
              onPress={() => handleTabPress('register')}
              activeOpacity={0.85}
            >
              <Text
                style={[
                  styles.tabDockText,
                  activeTab === 'register' && styles.tabDockTextActive,
                ]}
              >
                Registro
              </Text>
              {isOpen && activeTab === 'register' && <View style={styles.activeTabIndicator} />}
            </TouchableOpacity>
          </View>

          {/* Drag Handle Bar and Dismiss Button */}
          <View style={[styles.handleRow, { paddingBottom: isOpen ? 6 : Math.max(bottomInset, 16) }]}>
            <View style={styles.dragPillBar} />
            {isOpen && (
              <TouchableOpacity
                style={styles.closeButton}
                onPress={closeDrawer}
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
              >
                <Ionicons name="chevron-down" size={22} color="#7E9990" />
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Drawer Body Forms */}
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.formContainer}
        >
          <ScrollView
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={[styles.scrollContent, { paddingBottom: bottomInset + 30 }]}
          >
            {activeTab === 'login' ? (
              /* LOGIN FORM */
              <View style={styles.formSection}>
                <View style={styles.formTitleRow}>
                  <Text style={styles.formTitle}>Iniciar sesión</Text>
                  <Text style={styles.formSubtitle}>
                    Inicia sesión para acceder a tu panel de monitoreo
                  </Text>
                </View>

                {/* Email Field */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Correo electrónico</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'loginEmail' && styles.inputContainerFocused,
                    ]}
                  >
                    <Ionicons
                      name="mail-outline"
                      size={20}
                      color={focusedInput === 'loginEmail' ? '#00E676' : '#7E9990'}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.textInput}
                      placeholder="ejemplo@zentheris.com"
                      placeholderTextColor="#5A776D"
                      keyboardType="email-address"
                      autoCapitalize="none"
                      value={loginEmail}
                      onChangeText={setLoginEmail}
                      onFocus={() => setFocusedInput('loginEmail')}
                      onBlur={() => setFocusedInput(null)}
                    />
                  </View>
                </View>

                {/* Password Field */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Contraseña</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'loginPassword' && styles.inputContainerFocused,
                    ]}
                  >
                    <Ionicons
                      name="lock-closed-outline"
                      size={20}
                      color={focusedInput === 'loginPassword' ? '#00E676' : '#7E9990'}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.textInput}
                      placeholder="••••••••••••"
                      placeholderTextColor="#5A776D"
                      secureTextEntry={!showLoginPassword}
                      value={loginPassword}
                      onChangeText={setLoginPassword}
                      onFocus={() => setFocusedInput('loginPassword')}
                      onBlur={() => setFocusedInput(null)}
                    />
                    <TouchableOpacity
                      onPress={() => setShowLoginPassword(!showLoginPassword)}
                      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                    >
                      <Ionicons
                        name={showLoginPassword ? 'eye-off-outline' : 'eye-outline'}
                        size={20}
                        color="#7E9990"
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Forgot Password Link */}
                <TouchableOpacity
                  style={styles.forgotPasswordContainer}
                  onPress={() =>
                    Alert.alert(
                      'Recuperar Contraseña',
                      'Te enviaremos un correo con las instrucciones para restablecerla.'
                    )
                  }
                >
                  <Text style={styles.forgotPasswordText}>¿Olvidaste tu contraseña?</Text>
                </TouchableOpacity>

                {/* Submit Button */}
                <TouchableOpacity
                  style={styles.primaryButton}
                  onPress={handleLoginSubmit}
                  disabled={isLoading}
                  activeOpacity={0.85}
                >
                  {isLoading ? (
                    <ActivityIndicator color="#0D1F1A" />
                  ) : (
                    <Text style={styles.primaryButtonText}>Iniciar sesión</Text>
                  )}
                </TouchableOpacity>

                {/* Bottom switch link */}
                <View style={styles.switchModeContainer}>
                  <Text style={styles.switchModePrompt}>¿No tienes una cuenta? </Text>
                  <TouchableOpacity onPress={() => setActiveTab('register')}>
                    <Text style={styles.switchModeLink}>Regístrate aquí</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              /* REGISTER FORM */
              <View style={styles.formSection}>
                <View style={styles.formTitleRow}>
                  <Text style={styles.formTitle}>Crear Cuenta</Text>
                  <Text style={styles.formSubtitle}>
                    Comienza a optimizar y controlar tu energía con Zentheris
                  </Text>
                </View>

                {/* Full Name */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Nombre completo</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerName' && styles.inputContainerFocused,
                    ]}
                  >
                    <Ionicons
                      name="person-outline"
                      size={20}
                      color={focusedInput === 'registerName' ? '#00E676' : '#7E9990'}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.textInput}
                      placeholder="Juan Pérez"
                      placeholderTextColor="#5A776D"
                      value={registerName}
                      onChangeText={setRegisterName}
                      onFocus={() => setFocusedInput('registerName')}
                      onBlur={() => setFocusedInput(null)}
                    />
                  </View>
                </View>

                {/* Email */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Correo electrónico</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerEmail' && styles.inputContainerFocused,
                    ]}
                  >
                    <Ionicons
                      name="mail-outline"
                      size={20}
                      color={focusedInput === 'registerEmail' ? '#00E676' : '#7E9990'}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.textInput}
                      placeholder="ejemplo@zentheris.com"
                      placeholderTextColor="#5A776D"
                      keyboardType="email-address"
                      autoCapitalize="none"
                      value={registerEmail}
                      onChangeText={setRegisterEmail}
                      onFocus={() => setFocusedInput('registerEmail')}
                      onBlur={() => setFocusedInput(null)}
                    />
                  </View>
                </View>

                {/* Password */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Contraseña</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerPassword' && styles.inputContainerFocused,
                    ]}
                  >
                    <Ionicons
                      name="lock-closed-outline"
                      size={20}
                      color={focusedInput === 'registerPassword' ? '#00E676' : '#7E9990'}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.textInput}
                      placeholder="Mínimo 6 caracteres"
                      placeholderTextColor="#5A776D"
                      secureTextEntry={!showRegisterPassword}
                      value={registerPassword}
                      onChangeText={setRegisterPassword}
                      onFocus={() => setFocusedInput('registerPassword')}
                      onBlur={() => setFocusedInput(null)}
                    />
                    <TouchableOpacity
                      onPress={() => setShowRegisterPassword(!showRegisterPassword)}
                      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                    >
                      <Ionicons
                        name={showRegisterPassword ? 'eye-off-outline' : 'eye-outline'}
                        size={20}
                        color="#7E9990"
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Confirm Password */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Confirmar contraseña</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerConfirm' && styles.inputContainerFocused,
                    ]}
                  >
                    <Ionicons
                      name="shield-checkmark-outline"
                      size={20}
                      color={focusedInput === 'registerConfirm' ? '#00E676' : '#7E9990'}
                      style={styles.inputIcon}
                    />
                    <TextInput
                      style={styles.textInput}
                      placeholder="Repite tu contraseña"
                      placeholderTextColor="#5A776D"
                      secureTextEntry={!showRegisterConfirmPassword}
                      value={registerConfirmPassword}
                      onChangeText={setRegisterConfirmPassword}
                      onFocus={() => setFocusedInput('registerConfirm')}
                      onBlur={() => setFocusedInput(null)}
                    />
                    <TouchableOpacity
                      onPress={() =>
                        setShowRegisterConfirmPassword(!showRegisterConfirmPassword)
                      }
                      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                    >
                      <Ionicons
                        name={showRegisterConfirmPassword ? 'eye-off-outline' : 'eye-outline'}
                        size={20}
                        color="#7E9990"
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Submit Button */}
                <TouchableOpacity
                  style={styles.primaryButton}
                  onPress={handleRegisterSubmit}
                  disabled={isLoading}
                  activeOpacity={0.85}
                >
                  {isLoading ? (
                    <ActivityIndicator color="#0D1F1A" />
                  ) : (
                    <Text style={styles.primaryButtonText}>Registrarse</Text>
                  )}
                </TouchableOpacity>

                {/* Bottom switch link */}
                <View style={styles.switchModeContainer}>
                  <Text style={styles.switchModePrompt}>¿Ya tienes una cuenta? </Text>
                  <TouchableOpacity onPress={() => setActiveTab('login')}>
                    <Text style={styles.switchModeLink}>Inicia sesión</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </ScrollView>
        </KeyboardAvoidingView>
      </Animated.View>
    </View>
  );
};

export default LoginScreen;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D1F1A',
    justifyContent: 'space-between',
  },

  /* Center Branding */
  brandingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoWrapper: {
    width: 86,
    height: 155,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 18,
  },
  logoImage: {
    width: '100%',
    height: '100%',
  },
  brandTitle: {
    color: '#FFFFFF',
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: 0.5,
  },

  /* Backdrop */
  backdrop: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#000000',
    zIndex: 10,
  },

  /* Sliding Drawer Container */
  drawerContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: '#162B25',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    zIndex: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
    elevation: 20,
    overflow: 'hidden',
  },

  /* Drawer Top Area with Tabs & Drag Bar */
  drawerHeaderArea: {
    backgroundColor: '#162B25',
    paddingTop: 8,
  },
  dockTabsRow: {
    flexDirection: 'row',
    paddingHorizontal: 8,
    alignItems: 'flex-end',
    justifyContent: 'space-between',
  },
  tabDockButton: {
    flex: 1,
    backgroundColor: '#162B25',
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    position: 'relative',
  },
  tabDockButtonLeft: {
    marginRight: 2,
  },
  tabDockButtonRight: {
    marginLeft: 2,
  },
  tabDockButtonActive: {
    backgroundColor: '#1A332C',
  },
  tabDividerNotch: {
    width: 4,
    height: '100%',
  },
  tabDockText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#94A39F',
  },
  tabDockTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  activeTabIndicator: {
    position: 'absolute',
    bottom: 2,
    width: 32,
    height: 3,
    borderRadius: 2,
    backgroundColor: '#00E676',
  },

  /* Drag handle */
  handleRow: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 6,
    position: 'relative',
  },
  dragPillBar: {
    width: 48,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#4E6B60',
  },
  closeButton: {
    position: 'absolute',
    right: 18,
    top: -2,
    padding: 6,
  },

  /* Form Container */
  formContainer: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 16,
  },
  formSection: {
    width: '100%',
  },
  formTitleRow: {
    marginBottom: 20,
  },
  formTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 6,
  },
  formSubtitle: {
    fontSize: 14,
    color: '#8CA59C',
    lineHeight: 20,
  },

  /* Inputs */
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#B0C4BC',
    marginBottom: 8,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0D1F1A',
    borderRadius: 14,
    borderWidth: 1.2,
    borderColor: '#233E35',
    paddingHorizontal: 14,
    height: 52,
  },
  inputContainerFocused: {
    borderColor: '#00E676',
    backgroundColor: '#0B1B17',
  },
  inputIcon: {
    marginRight: 10,
  },
  textInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 15,
    height: '100%',
  },

  /* Links & Buttons */
  forgotPasswordContainer: {
    alignSelf: 'flex-end',
    marginBottom: 20,
    marginTop: 2,
  },
  forgotPasswordText: {
    color: '#00E676',
    fontSize: 13,
    fontWeight: '500',
  },
  primaryButton: {
    backgroundColor: '#00E676',
    height: 54,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#00E676',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
    marginBottom: 20,
  },
  primaryButtonText: {
    color: '#071A14',
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  switchModeContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 4,
  },
  switchModePrompt: {
    color: '#8CA59C',
    fontSize: 14,
  },
  switchModeLink: {
    color: '#00E676',
    fontSize: 14,
    fontWeight: '700',
  },
});
