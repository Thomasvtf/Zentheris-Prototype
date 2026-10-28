import React from 'react';
import { LoginScreen, AuthScreenProps } from './LoginScreen';

export const RegisterScreen: React.FC<AuthScreenProps> = (props) => {
  return <LoginScreen initialTab="register" initialOpen={true} {...props} />;
};

export default RegisterScreen;

