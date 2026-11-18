/**
 * Fuentes de datos (RN-XVI-06, sección 6.16): consulta de solo lectura de la fuente
 * principal y de los sensores por zona. Contrato: GET /hogares/{hogar_id}/fuentes-datos
 * (obtenerFuentesDatos). Mapa: docs/MAPA-DE-INTEGRACION.md, fila 31.
 *
 * - `null` es «sin dato», nunca cero (formatNumber(null) → «—»).
 * - Sin permiso de consumo (`valores_ocultos`), se ven nombre y estado, no los kW (N4).
 * - El estado «Sin datos» / «Pausado» no es severidad: sin amarillo ni rojo.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextStyle,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { getDataSources } from '@/api/consumption';
import { toErrorTextKey } from '@/api/errors';
import type { SuccessBody } from '@/api/client';
import { DECIMALES, formatNumber } from '@/format';
import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { t } from '@/texts';

type DataSources = SuccessBody<'/hogares/{hogar_id}/fuentes-datos', 'get'>;
type SourceState = 'activo' | 'pausado' | 'sin_datos';

type DataSourcesState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; data: DataSources };

/**
 * Hook de datos de la pantalla (cargando, error y datos).
 * TODO(pendiente: hogarId): aún no existe el estado de sesión/hogar (GET /hogares/actual,
 * fila 12 del mapa). Mientras tanto la pantalla recibe `hogarId` por prop; sin él muestra
 * `error.app.no_encontrado`. Al existir `useDataSourcesData.ts` y el provider de React
 * Query, este hook se mueve a ese archivo con useQuery(queryKey('obtenerFuentesDatos', …)).
 */
function useDataSourcesData(hogarId: string | null) {
  const [state, setState] = useState<DataSourcesState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!hogarId) {
      setState({ status: 'error', errorKey: 'error.app.no_encontrado' });
      return;
    }
    let cancelled = false;
    setState({ status: 'loading' });
    getDataSources(hogarId)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', errorKey: toErrorTextKey(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [hogarId, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, retry };
}

/** Estilo de texto desde los tokens de tipografía. */
function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}

const BOGOTA_OFFSET_MS = -5 * 60 * 60 * 1000;

function hourLabel(iso: string): string {
  const local = new Date(new Date(iso).getTime() + BOGOTA_OFFSET_MS);
  return `${String(local.getUTCHours()).padStart(2, '0')}:00`;
}

/** «14:00–15:00» en hora de Bogotá, para la nota al pie. */
function intervalLabel(hora: DataSources['hora']): string {
  return `${hourLabel(hora.inicio)}–${hourLabel(hora.fin)}`;
}

const ZONE_ICONS: Record<string, { lib: 'ion' | 'mci'; name: string }> = {
  Cocina: { lib: 'mci', name: 'fridge-outline' },
  Dormitorio: { lib: 'ion', name: 'bed-outline' },
  Oficina: { lib: 'ion', name: 'desktop-outline' },
  Sala: { lib: 'mci', name: 'sofa-outline' },
};

function ZoneIcon({ zona }: { zona: string }) {
  const icon = ZONE_ICONS[zona] ?? { lib: 'ion', name: 'location-outline' };
  return icon.lib === 'mci' ? (
    <MaterialCommunityIcons name={icon.name as never} size={22} color={colors['text-muted']} />
  ) : (
    <Ionicons name={icon.name as never} size={22} color={colors['text-muted']} />
  );
}

/** Estado = ícono + palabra (nunca solo color). */
function SourceStatus({ estado }: { estado: SourceState }) {
  const active = estado === 'activo';
  const icon =
    estado === 'activo'
      ? 'checkmark-circle-outline'
      : estado === 'pausado'
        ? 'pause-circle-outline'
        : 'sparkles-outline';
  const color = active ? colors['text-accent'] : colors['text-muted'];
  return (
    <View style={styles.statusRow}>
      <Ionicons name={icon} size={15} color={color} />
      <Text style={[styles.statusText, { color }]}>{t(`fuentes.estado_${estado}`)}</Text>
    </View>
  );
}

interface SourceRowProps {
  icon: React.ReactNode;
  nombre: string;
  detalle: string;
  potenciaKw: number | null;
  estado: SourceState;
  mostrarValor: boolean;
}

function SourceRow({ icon, nombre, detalle, potenciaKw, estado, mostrarValor }: SourceRowProps) {
  return (
    <View style={styles.card}>
      <View style={styles.iconBox}>{icon}</View>
      <View style={styles.cardCenter}>
        <Text style={styles.cardTitle}>{nombre}</Text>
        <Text style={styles.cardSubtitle}>{detalle}</Text>
      </View>
      <View style={styles.cardRight}>
        {mostrarValor && (
          <View style={styles.valueRow}>
            <Text style={styles.metricNumber}>{formatNumber(potenciaKw, DECIMALES.kW)}</Text>
            <Text style={styles.metricUnit}> kW</Text>
          </View>
        )}
        <SourceStatus estado={estado} />
      </View>
    </View>
  );
}

function SkeletonRows() {
  return (
    <View accessibilityRole="progressbar" accessibilityLabel={t('comun.cargando')}>
      {[0, 1, 2, 3].map((i) => (
        <View key={i} style={[styles.card, styles.skeleton]} />
      ))}
    </View>
  );
}

function ErrorNotice({ errorKey, onRetry }: { errorKey: string; onRetry: () => void }) {
  return (
    <View style={styles.errorBox} accessibilityRole="alert">
      <Ionicons name="alert-circle-outline" size={22} color={colors['status-error-text']} />
      <View style={styles.errorTexts}>
        <Text style={styles.errorTitle}>{t(`${errorKey}.titulo`)}</Text>
        <Text style={styles.errorBody}>{t(`${errorKey}.cuerpo`)}</Text>
        <TouchableOpacity
          onPress={onRetry}
          activeOpacity={0.7}
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          accessibilityRole="button"
        >
          <Text style={styles.retryText}>{t('error.app.desconocido.accion')}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

export interface FuentesDatosScreenProps {
  /** TODO(pendiente: hogarId): vendrá del estado de sesión/hogar cuando exista. */
  hogarId?: string | null;
}

export function FuentesDatosScreen({ hogarId = null }: FuentesDatosScreenProps) {
  const router = useRouter();
  const { state, retry } = useDataSourcesData(hogarId);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />

      <View style={styles.header}>
        <TouchableOpacity
          style={styles.headerBtn}
          activeOpacity={0.7}
          onPress={() => router.back()}
          hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
          accessibilityRole="button"
          accessibilityLabel={t('a11y.volver')}
        >
          <Ionicons name="chevron-back" size={24} color={colors['text-primary']} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('fuentes.encabezado')}</Text>
        <View style={styles.headerBtn} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.infoBanner}>
          <Ionicons
            name="information-circle-outline"
            size={22}
            color={colors['text-accent']}
            style={styles.infoIcon}
          />
          <Text style={styles.infoBannerText}>{t('fuentes.intro')}</Text>
        </View>

        {state.status === 'loading' && <SkeletonRows />}

        {state.status === 'error' && <ErrorNotice errorKey={state.errorKey} onRetry={retry} />}

        {state.status === 'ready' && (
          <>
            {state.data.valores_ocultos && (
              // Sin permiso de consumo: se ven fuentes y estado, sin kW (N4).
              <View style={styles.noticeBox} accessibilityRole="alert">
                <Text style={styles.noticeTitle}>{t('fuentes.sin_permiso_titulo')}</Text>
                <Text style={styles.noticeBody}>{t('fuentes.sin_permiso_cuerpo')}</Text>
              </View>
            )}

            <Text style={styles.sectionTitle}>{t('fuentes.principal')}</Text>
            <SourceRow
              icon={<Ionicons name="flash-outline" size={22} color={colors['text-accent']} />}
              nombre={state.data.fuente_principal.nombre}
              detalle={t('fuentes.principal_suma')}
              potenciaKw={state.data.fuente_principal.potencia_kw}
              // «inactiva» se muestra como «Pausado» (el contrato solo trae activa | inactiva).
              estado={state.data.fuente_principal.estado === 'activa' ? 'activo' : 'pausado'}
              mostrarValor={!state.data.valores_ocultos}
            />

            <Text style={[styles.sectionTitle, styles.sectionSpaced]}>{t('fuentes.sensores')}</Text>
            {state.data.sensores.length === 0 ? (
              // TODO(pendiente: texto de estado vacío de fuentes): el catálogo no lo define.
              <Text style={styles.emptyText}>{t('fuentes.estado_sin_datos')}</Text>
            ) : (
              state.data.sensores.map((sensor) => (
                <SourceRow
                  key={sensor.id}
                  icon={<ZoneIcon zona={sensor.zona_nombre} />}
                  nombre={sensor.nombre}
                  detalle={sensor.zona_nombre}
                  potenciaKw={sensor.potencia_kw}
                  estado={sensor.estado}
                  mostrarValor={!state.data.valores_ocultos}
                />
              ))
            )}

            <Text style={styles.footerNote}>
              {t('fuentes.pie', { intervalo: intervalLabel(state.data.hora) })}
            </Text>
          </>
        )}

        <View style={styles.bottomSpace} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors['background-default'],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing[16],
    paddingTop: spacing[12],
    paddingBottom: spacing[8],
  },
  headerBtn: {
    width: sizes['iconButton-size'],
    height: sizes['iconButton-size'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    ...textStyle('display-m'),
    color: colors['text-primary'],
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: spacing[16],
    paddingTop: spacing[8],
  },

  infoBanner: {
    backgroundColor: colors['status-info-bg'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['status-info-border'],
    padding: spacing[16],
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing[20],
  },
  infoIcon: {
    marginRight: spacing[12],
  },
  infoBannerText: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    flex: 1,
  },

  sectionTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
    marginBottom: spacing[12],
  },
  sectionSpaced: {
    marginTop: spacing[20],
  },

  card: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing[12],
  },
  skeleton: {
    height: 76,
    backgroundColor: colors['background-surfaceAlt'],
  },
  iconBox: {
    width: spacing[40] + spacing[4],
    height: spacing[40] + spacing[4],
    borderRadius: radius.lg,
    backgroundColor: colors['background-surfaceAlt'],
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing[12],
  },
  cardCenter: {
    flex: 1,
    marginRight: spacing[8],
  },
  cardTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  cardSubtitle: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
  },
  cardRight: {
    alignItems: 'flex-end',
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: spacing[4],
  },
  metricNumber: {
    ...textStyle('ui-m-semibold'),
    color: colors['text-primary'],
  },
  metricUnit: {
    ...textStyle('body-xs-medium'),
    color: colors['text-muted'],
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[4],
  },
  statusText: {
    ...textStyle('body-xs-medium'),
  },

  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing[12],
    backgroundColor: colors['status-error-bg'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['status-error-border'],
    padding: spacing[16],
  },
  errorTexts: {
    flex: 1,
    gap: spacing[4],
  },
  errorTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  errorBody: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },
  retryText: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-accent'],
    marginTop: spacing[8],
  },

  noticeBox: {
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    padding: spacing[16],
    marginBottom: spacing[20],
    gap: spacing[4],
  },
  noticeTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  noticeBody: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },

  emptyText: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },
  footerNote: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
    marginTop: spacing[8],
    marginBottom: spacing[16],
  },
  bottomSpace: {
    height: spacing[24],
  },
});
