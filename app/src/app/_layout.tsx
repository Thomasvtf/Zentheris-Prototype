import { Tabs } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

// Importa los SVGs exportados de Figma
import IconoPanel from '../../assets/icons/home.svg';
import IconoPanelActivo from '../../assets/icons/home_active.svg';
import IconoHistorial from '../../assets/icons/historial.svg';
import IconoHistorialActivo from '../../assets/icons/historial_active.svg';
import IconoZonas from '../../assets/icons/zonas.svg';
import IconoZonasActivo from '../../assets/icons/zonas_active.svg';
import IconoConsejos from '../../assets/icons/consejos.svg';
import IconoConsejosActivo from '../../assets/icons/consejos_active.svg';
import IconoConfiguracion from '../../assets/icons/configuracion.svg';
import IconoConfiguracionActivo from '../../assets/icons/configuracion_active.svg';

export default function Layout() {
  return (
    <>
      <StatusBar style="light" />
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarLabelPosition: 'below-icon',
          tabBarStyle: {
            backgroundColor: '#162B25',
            borderTopColor: '#FFFFFF14',
            height: 70,
            paddingBottom: 8,
            paddingTop: 8,
          },
          tabBarActiveTintColor: '#00E676',
          tabBarInactiveTintColor: '#64748B',
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: '500',
            marginTop: 2,
          },
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: 'Principal',
            tabBarIcon: ({ focused }) => focused ? (
              <IconoPanelActivo width={50} height={50}/>
            ) : (
              <IconoPanel width={20} height={20}/>
            ),
          }}
        />
        <Tabs.Screen
          name="historial"
          options={{
            title: 'Historial',
            tabBarIcon: ({ focused }) => focused ? (
              <IconoHistorialActivo width={50 } height={50}  />
            ) : (
              <IconoHistorial width={20} height={20}  />
            ),
          }}
        />
        <Tabs.Screen
          name="zonas"
          options={{
            title: 'Zonas',
            tabBarIcon: ({ focused }) => focused ? (
              <IconoZonasActivo width={50} height={50}  />
            ) : (
              <IconoZonas width={20} height={20}  />
            ),
          }}
        />
        <Tabs.Screen
          name="consejos"
          options={{
            title: 'Consejos',
            tabBarIcon: ({ focused }) => focused ? (
              <IconoConsejosActivo width={50} height={50}  />
            ) : (
              <IconoConsejos width={20} height={20}  />
            ),
          }}
        />
        <Tabs.Screen
            name="configuracion"
          options={{
            title: 'Configuración',
            tabBarIcon: ({ focused }) => focused ? (
              <IconoConfiguracionActivo width={50} height={50}  />
            ) : (
              <IconoConfiguracion width={20} height={20}  />
            ),
          }}
        />
      </Tabs>
    </>
  );
}