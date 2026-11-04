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

  const bottomInset = insets.bottom || 12;
  const CLOSED_DRAWER_HEIGHT = 82 + bottomInset;

  // Drawer open heights for each view
  const LOGIN_DRAWER_HEIGHT = Math.min(SCREEN_HEIGHT * 0.54, 450);
  const REGISTER_DRAWER_HEIGHT = Math.min(SCREEN_HEIGHT * 0.86, 710);

  // Active form tab ('login' | 'register')
  const [activeTab, setActiveTab] = useState<'login' | 'register'>(initialTab);
  const [isOpen, setIsOpen] = useState<boolean>(initialOpen);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const targetHeight = activeTab === 'login' ? LOGIN_DRAWER_HEIGHT : REGISTER_DRAWER_HEIGHT;
  const MAX_TRANSLATE_Y = targetHeight - CLOSED_DRAWER_HEIGHT;

  // Animated values
  const translateY = useRef(new Animated.Value(initialOpen ? 0 : MAX_TRANSLATE_Y)).current;
  const currentTranslateY = useRef(initialOpen ? 0 : MAX_TRANSLATE_Y);
  const heightAnim = useRef(new Animated.Value(targetHeight)).current;

  // Form states - Login
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);

  // Form states - Register
  const [registerName, setRegisterName] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPhone, setRegisterPhone] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [showRegisterConfirmPassword, setShowRegisterConfirmPassword] = useState(false);

  // Focus states for input styling
  const [focusedInput, setFocusedInput] = useState<string | null>(null);

  useEffect(() => {
    const listenerId = translateY.addListener((val) => {
      currentTranslateY.current = val.value;
    });
    return () => {
      translateY.removeListener(listenerId);
    };
  }, [translateY]);

  // Adjust height when tab changes while open
  useEffect(() => {
    const newHeight = activeTab === 'login' ? LOGIN_DRAWER_HEIGHT : REGISTER_DRAWER_HEIGHT;
    Animated.timing(heightAnim, {
      toValue: newHeight,
      duration: 250,
      useNativeDriver: false,
    }).start();
  }, [activeTab]);

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
        return Math.abs(gestureState.dy) > 7 && Math.abs(gestureState.dy) > Math.abs(gestureState.dx);
      },
      onPanResponderGrant: () => {
        translateY.extractOffset();
      },
      onPanResponderMove: (_, gestureState) => {
        const nextVal = currentTranslateY.current + gestureState.dy;
        if (nextVal >= 0 && nextVal <= MAX_TRANSLATE_Y) {
          translateY.setValue(gestureState.dy);
        }
      },
      onPanResponderRelease: (_, gestureState) => {
        translateY.flattenOffset();
        const movedY = currentTranslateY.current;

        if (gestureState.vy < -0.3) {
          openDrawer();
          return;
        }

        if (gestureState.vy > 0.) {
          closeDrawer();
          return;
        }

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

  // Password criteria check
  const hasMinLength = registerPassword.length >= 8;
  const hasUpperCase = /[A-Z]/.test(registerPassword);
  const hasNumber = /[0-9]/.test(registerPassword);

  // Handle Login submission
  const handleLoginSubmit = () => {
    if (!loginEmail.trim() || !loginPassword.trim()) {
      Alert.alert('Campos requeridos', 'Por favor ingresa tu correo y contraseña.');
      return;
    }

    setIsLoading(true);
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

      {/* Main Screen Branding / Header */}
      <View
        style={[
          styles.brandingContainer,
          isOpen
            ? activeTab === 'login'
              ? styles.brandingLoginOpen
              : styles.brandingRegisterOpen
            : { paddingBottom: CLOSED_DRAWER_HEIGHT },
        ]}
      >
        <View style={[styles.logoWrapper, isOpen && styles.logoWrapperOpen]}>
          <Image
            source={require('../../assets/images/zentheris-logo.png')}
            style={styles.logoImage}
            resizeMode="contain"
          />
        </View>

        {/* Dynamic Title & Subtitle */}
        {!isOpen ? (
          <Text style={styles.brandTitle}>Zentheris</Text>
        ) : activeTab === 'login' ? (
          <View style={styles.headerTextsWrapper}>
            <Text style={styles.openHeaderTitle}>Iniciar sesión</Text>
            <Text style={styles.openHeaderSubtitle}>
              Ingresa tus datos para acceder a la cuenta.
            </Text>
          </View>
        ) : (
          <View style={styles.headerTextsWrapper}>
            <Text style={styles.openHeaderTitle}>Crear cuenta</Text>
            <Text style={styles.openHeaderSubtitle}>
              Completa tus datos para crear tu cuenta.
            </Text>
          </View>
        )}
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
            height: heightAnim,
            transform: [{ translateY }],
          },
        ]}
      >
        {/* Gesture Area: Tabs Row + Handle Pill */}
        <View {...panResponder.panHandlers} style={styles.drawerHeaderArea}>
          {/* TABS ROW */}
          {!isOpen ? (
            /* CLOSED STATE: Double adjacent rounded tabs forming the center notch */
            <View style={styles.closedTabsRow}>
              <TouchableOpacity
                style={styles.closedTabLeft}
                onPress={() => openDrawer('login')}
                activeOpacity={0.88}
              >
                <Text style={styles.closedTabTextLeft}>Iniciar sesión</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.closedTabRight}
                onPress={() => openDrawer('register')}
                activeOpacity={0.88}
              >
                <Text style={styles.closedTabTextRight}>Registro</Text>
              </TouchableOpacity>
            </View>
          ) : (
            /* OPEN STATE: Folder tab shape with active tab elevated */
            <View style={styles.openTabsRow}>
              <TouchableOpacity
                style={[
                  styles.openTabButton,
                  activeTab === 'login' ? styles.openTabActiveLeft : styles.openTabInactive,
                ]}
                onPress={() => handleTabPress('login')}
                activeOpacity={0.88}
              >
                <Text
                  style={[
                    styles.openTabText,
                    activeTab === 'login' ? styles.openTabTextActive : styles.openTabTextInactive,
                  ]}
                >
                  Iniciar sesión
                </Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[
                  styles.openTabButton,
                  activeTab === 'register' ? styles.openTabActiveRight : styles.openTabInactive,
                ]}
                onPress={() => handleTabPress('register')}
                activeOpacity={0.88}
              >
                <Text
                  style={[
                    styles.openTabText,
                    activeTab === 'register' ? styles.openTabTextActive : styles.openTabTextInactive,
                  ]}
                >
                  Registrarse
                </Text>
              </TouchableOpacity>
            </View>
          )}

          {/* DRAG HANDLE BAR */}
          <View style={[styles.handleRow, { paddingBottom: isOpen ? 6 : Math.max(bottomInset, 16) }]}>
            <View style={styles.dragPillBar} />
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
                {/* Correo electronico */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Correo electrónico</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'loginEmail' && styles.inputContainerFocused,
                    ]}
                  >
                    <TextInput
                      style={styles.textInput}
                      placeholder="usuario123@gmail.com"
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

                {/* Contrasena */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Contraseña</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'loginPassword' && styles.inputContainerFocused,
                    ]}
                  >
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
                        name={showLoginPassword ? 'eye-outline' : 'eye-off-outline'}
                        size={20}
                        color="#8DA59E"
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
                    <ActivityIndicator color="#0C1F1B" />
                  ) : (
                    <Text style={styles.primaryButtonText}>Iniciar sesión</Text>
                  )}
                </TouchableOpacity>

                {/* Bottom switch link */}
                <View style={styles.switchModeContainer}>
                  <Text style={styles.switchModePrompt}>¿No tienes cuenta? </Text>
                  <TouchableOpacity onPress={() => setActiveTab('register')}>
                    <Text style={styles.switchModeLink}>Crear cuenta</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              /* REGISTER FORM */
              <View style={styles.formSection}>
                {/* Nombre */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Nombre</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerName' && styles.inputContainerFocused,
                    ]}
                  >
                    <TextInput
                      style={styles.textInput}
                      placeholder="Thomas Vargas"
                      placeholderTextColor="#5A776D"
                      value={registerName}
                      onChangeText={setRegisterName}
                      onFocus={() => setFocusedInput('registerName')}
                      onBlur={() => setFocusedInput(null)}
                    />
                  </View>
                </View>

                {/* Correo electronico */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Correo electrónico</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerEmail' && styles.inputContainerFocused,
                    ]}
                  >
                    <TextInput
                      style={styles.textInput}
                      placeholder="usuario123@gmail.com"
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

                {/* Numero de celular */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Número de celular</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerPhone' && styles.inputContainerFocused,
                    ]}
                  >
                    <TextInput
                      style={styles.textInput}
                      placeholder="0000 000 000"
                      placeholderTextColor="#5A776D"
                      keyboardType="phone-pad"
                      value={registerPhone}
                      onChangeText={setRegisterPhone}
                      onFocus={() => setFocusedInput('registerPhone')}
                      onBlur={() => setFocusedInput(null)}
                    />
                  </View>
                </View>

                {/* Contrasena */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Contraseña</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerPassword' && styles.inputContainerFocused,
                    ]}
                  >
                    <TextInput
                      style={styles.textInput}
                      placeholder="••••••••••••"
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
                        name={showRegisterPassword ? 'eye-outline' : 'eye-off-outline'}
                        size={20}
                        color="#8DA59E"
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Repetir contrasena */}
                <View style={styles.inputGroup}>
                  <Text style={styles.inputLabel}>Repetir contraseña</Text>
                  <View
                    style={[
                      styles.inputContainer,
                      focusedInput === 'registerConfirm' && styles.inputContainerFocused,
                    ]}
                  >
                    <TextInput
                      style={styles.textInput}
                      placeholder="••••••••••••"
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
                        name={showRegisterConfirmPassword ? 'eye-outline' : 'eye-off-outline'}
                        size={20}
                        color="#8DA59E"
                      />
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Password Criteria Box */}
                <View style={styles.criteriaBox}>
                  <Text style={styles.criteriaTitle}>Tu contraseña debe incluir:</Text>
                  <View style={styles.criteriaPillsRow}>
                    <View style={[styles.criteriaPill, hasMinLength && styles.criteriaPillActive]}>
                      <Text style={[styles.criteriaPillText, hasMinLength && styles.criteriaPillTextActive]}>
                        8 caracteres
                      </Text>
                    </View>
                    <View style={[styles.criteriaPill, hasUpperCase && styles.criteriaPillActive]}>
                      <Text style={[styles.criteriaPillText, hasUpperCase && styles.criteriaPillTextActive]}>
                        Una mayúscula
                      </Text>
                    </View>
                    <View style={[styles.criteriaPill, hasNumber && styles.criteriaPillActive]}>
                      <Text style={[styles.criteriaPillText, hasNumber && styles.criteriaPillTextActive]}>
                        Un número
                      </Text>
                    </View>
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
                    <ActivityIndicator color="#0C1F1B" />
                  ) : (
                    <Text style={styles.primaryButtonText}>Crear cuenta</Text>
                  )}
                </TouchableOpacity>

                {/* Bottom switch link */}
                <View style={styles.switchModeContainer}>
                  <Text style={styles.switchModePrompt}>¿Ya tienes cuenta? </Text>
                  <TouchableOpacity onPress={() => setActiveTab('login')}>
                    <Text style={styles.switchModeLink}>Iniciar sesión</Text>
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

  /* Center Branding / Header */
  brandingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  brandingLoginOpen: {
    justifyContent: 'flex-start',
    paddingTop: 52,
  },
  brandingRegisterOpen: {
    justifyContent: 'flex-start',
    paddingTop: 10,
  },
  logoWrapper: {
    width: 86,
    height: 155,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  logoWrapperOpen: {
    width: 48,
    height: 84,
    marginBottom: 8,
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
  headerTextsWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  openHeaderTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 6,
    textAlign: 'center',
  },
  openHeaderSubtitle: {
    fontSize: 13,
    color: '#8CA59C',
    textAlign: 'center',
    lineHeight: 18,
  },

  /* Backdrop */
  backdrop: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 10,
  },

  /* Sliding Drawer Container */
  drawerContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'transparent',
    zIndex: 20,
    overflow: 'hidden',
  },

  drawerHeaderArea: {
    backgroundColor: 'transparent',
  },

  /* CLOSED STATE: Dual adjacent rounded tabs */
  closedTabsRow: {
    flexDirection: 'row',
    height: 52,
    backgroundColor: 'transparent',
  },
  closedTabLeft: {
    flex: 1,
    height: 52,
    backgroundColor: '#162B25',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closedTabRight: {
    flex: 1,
    height: 52,
    backgroundColor: '#162B25',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closedTabTextLeft: {
    fontSize: 14,
    fontWeight: '600',
    color: '#C4D4CF',
  },
  closedTabTextRight: {
    fontSize: 14,
    fontWeight: '600',
    color: '#A3B4AF',
  },

  /* OPEN STATE: Folder tab with active tab elevated */
  openTabsRow: {
    flexDirection: 'row',
    height: 48,
    alignItems: 'flex-end',
    backgroundColor: '#0D1F1A',
  },
  openTabButton: {
    flex: 1,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  openTabActiveLeft: {
    backgroundColor: '#162B25',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  openTabActiveRight: {
    backgroundColor: '#162B25',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  openTabInactive: {
    backgroundColor: 'transparent',
  },
  openTabText: {
    fontSize: 14,
  },
  openTabTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  openTabTextInactive: {
    color: '#7A918A',
    fontWeight: '500',
  },

  /* Handle row below tabs inside drawer body */
  handleRow: {
    backgroundColor: '#162B25',
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 10,
    paddingBottom: 4,
  },
  dragPillBar: {
    width: 46,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#798B85',
  },

  /* Form Container */
  formContainer: {
    flex: 1,
    backgroundColor: '#162B25',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  formSection: {
    width: '100%',
  },

  /* Inputs */
  inputGroup: {
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '500',
    color: '#A6BBB4',
    marginBottom: 6,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0C1F1B',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1D3830',
    paddingHorizontal: 12,
    height: 44,
  },
  inputContainerFocused: {
    borderColor: '#68CDA1',
    backgroundColor: '#0A1A17',
  },
  textInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 14,
    height: '100%',
  },

  /* Criteria Box */
  criteriaBox: {
    backgroundColor: '#0C1F1B',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#162B25',
  },
  criteriaTitle: {
    color: '#849C94',
    fontSize: 11,
    marginBottom: 8,
    fontWeight: '500',
  },
  criteriaPillsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  criteriaPill: {
    backgroundColor: '#122621',
    borderRadius: 14,
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderWidth: 1,
    borderColor: '#1D352E',
  },
  criteriaPillActive: {
    borderColor: '#68CDA1',
    backgroundColor: '#18372F',
  },
  criteriaPillText: {
    color: '#657E77',
    fontSize: 11,
  },
  criteriaPillTextActive: {
    color: '#68CDA1',
    fontWeight: '600',
  },

  /* Links & Buttons */
  forgotPasswordContainer: {
    alignSelf: 'flex-end',
    marginBottom: 16,
    marginTop: 2,
  },
  forgotPasswordText: {
    color: '#68CDA1',
    fontSize: 12,
    fontWeight: '500',
  },
  primaryButton: {
    backgroundColor: '#68CDA1',
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#68CDA1',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
    marginBottom: 16,
  },
  primaryButtonText: {
    color: '#0C1F1B',
    fontSize: 15,
    fontWeight: '700',
  },
  switchModeContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
    marginBottom: 10,
  },
  switchModePrompt: {
    color: '#8CA59C',
    fontSize: 13,
  },
  switchModeLink: {
    color: '#68CDA1',
    fontSize: 13,
    fontWeight: '700',
  },
});
