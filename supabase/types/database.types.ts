export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      alertas: {
        Row: {
          categoria: string
          clave_evento: string
          created_at: string
          hogar_id: string
          id: string
          mensaje: string
          regla_origen: string
          severidad: string
          titulo: string
          updated_at: string
          zona_id: string | null
        }
        Insert: {
          categoria: string
          clave_evento: string
          created_at?: string
          hogar_id: string
          id?: string
          mensaje: string
          regla_origen: string
          severidad: string
          titulo: string
          updated_at?: string
          zona_id?: string | null
        }
        Update: {
          categoria?: string
          clave_evento?: string
          created_at?: string
          hogar_id?: string
          id?: string
          mensaje?: string
          regla_origen?: string
          severidad?: string
          titulo?: string
          updated_at?: string
          zona_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "alertas_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: false
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alertas_zona_id_fkey"
            columns: ["zona_id"]
            isOneToOne: false
            referencedRelation: "zonas"
            referencedColumns: ["id"]
          },
        ]
      }
      alertas_usuario: {
        Row: {
          alerta_id: string
          created_at: string
          leida_en: string | null
          updated_at: string
          usuario_id: string
        }
        Insert: {
          alerta_id: string
          created_at?: string
          leida_en?: string | null
          updated_at?: string
          usuario_id: string
        }
        Update: {
          alerta_id?: string
          created_at?: string
          leida_en?: string | null
          updated_at?: string
          usuario_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "alertas_usuario_alerta_id_fkey"
            columns: ["alerta_id"]
            isOneToOne: false
            referencedRelation: "alertas"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alertas_usuario_usuario_id_fkey"
            columns: ["usuario_id"]
            isOneToOne: false
            referencedRelation: "usuarios"
            referencedColumns: ["id"]
          },
        ]
      }
      consejos: {
        Row: {
          categoria: string
          created_at: string
          descripcion: string
          hogar_id: string
          id: string
          prioridad: string
          regla_origen: string
          titulo: string
          updated_at: string
          zona_id: string | null
        }
        Insert: {
          categoria: string
          created_at?: string
          descripcion: string
          hogar_id: string
          id?: string
          prioridad: string
          regla_origen: string
          titulo: string
          updated_at?: string
          zona_id?: string | null
        }
        Update: {
          categoria?: string
          created_at?: string
          descripcion?: string
          hogar_id?: string
          id?: string
          prioridad?: string
          regla_origen?: string
          titulo?: string
          updated_at?: string
          zona_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "consejos_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: false
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "consejos_zona_id_fkey"
            columns: ["zona_id"]
            isOneToOne: false
            referencedRelation: "zonas"
            referencedColumns: ["id"]
          },
        ]
      }
      consejos_usuario: {
        Row: {
          completada_en: string | null
          consejo_id: string
          created_at: string
          estado: string
          id: string
          updated_at: string
          usuario_id: string
        }
        Insert: {
          completada_en?: string | null
          consejo_id: string
          created_at?: string
          estado: string
          id?: string
          updated_at?: string
          usuario_id: string
        }
        Update: {
          completada_en?: string | null
          consejo_id?: string
          created_at?: string
          estado?: string
          id?: string
          updated_at?: string
          usuario_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "consejos_usuario_consejo_id_fkey"
            columns: ["consejo_id"]
            isOneToOne: false
            referencedRelation: "consejos"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "consejos_usuario_usuario_id_fkey"
            columns: ["usuario_id"]
            isOneToOne: false
            referencedRelation: "usuarios"
            referencedColumns: ["id"]
          },
        ]
      }
      fuentes_principales: {
        Row: {
          created_at: string
          estado: string
          hogar_id: string
          id: string
          nombre: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          estado: string
          hogar_id: string
          id?: string
          nombre: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          estado?: string
          hogar_id?: string
          id?: string
          nombre?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "fuentes_principales_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: true
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
        ]
      }
      hogar_miembros: {
        Row: {
          created_at: string
          estado: string
          fecha_ingreso: string
          fecha_salida: string | null
          hogar_id: string
          id: string
          rol: string
          updated_at: string
          usuario_id: string | null
        }
        Insert: {
          created_at?: string
          estado: string
          fecha_ingreso: string
          fecha_salida?: string | null
          hogar_id: string
          id?: string
          rol: string
          updated_at?: string
          usuario_id?: string | null
        }
        Update: {
          created_at?: string
          estado?: string
          fecha_ingreso?: string
          fecha_salida?: string | null
          hogar_id?: string
          id?: string
          rol?: string
          updated_at?: string
          usuario_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "hogar_miembros_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: false
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "hogar_miembros_usuario_id_fkey"
            columns: ["usuario_id"]
            isOneToOne: false
            referencedRelation: "usuarios"
            referencedColumns: ["id"]
          },
        ]
      }
      hogares: {
        Row: {
          ciudad: string | null
          created_at: string
          estrato: number | null
          id: string
          nombre: string
          numero_personas: number | null
          perfil_simulacion_id: string
          permiso_modificar_metas: boolean
          permiso_recibir_alertas: boolean
          permiso_ver_consumo_actual: boolean
          permiso_ver_historial: boolean
          tipo_vivienda: string
          trabajo_estudio_casa: boolean | null
          updated_at: string
        }
        Insert: {
          ciudad?: string | null
          created_at?: string
          estrato?: number | null
          id?: string
          nombre: string
          numero_personas?: number | null
          perfil_simulacion_id: string
          permiso_modificar_metas?: boolean
          permiso_recibir_alertas?: boolean
          permiso_ver_consumo_actual?: boolean
          permiso_ver_historial?: boolean
          tipo_vivienda: string
          trabajo_estudio_casa?: boolean | null
          updated_at?: string
        }
        Update: {
          ciudad?: string | null
          created_at?: string
          estrato?: number | null
          id?: string
          nombre?: string
          numero_personas?: number | null
          perfil_simulacion_id?: string
          permiso_modificar_metas?: boolean
          permiso_recibir_alertas?: boolean
          permiso_ver_consumo_actual?: boolean
          permiso_ver_historial?: boolean
          tipo_vivienda?: string
          trabajo_estudio_casa?: boolean | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "hogares_perfil_simulacion_id_fkey"
            columns: ["perfil_simulacion_id"]
            isOneToOne: false
            referencedRelation: "perfiles_simulacion"
            referencedColumns: ["id"]
          },
        ]
      }
      invitaciones_hogar: {
        Row: {
          correo_invitado: string
          created_at: string
          estado: string
          expira_en: string
          hogar_id: string
          id: string
          invitado_por: string | null
          respondida_en: string | null
          token_hash: string
          updated_at: string
        }
        Insert: {
          correo_invitado: string
          created_at?: string
          estado: string
          expira_en: string
          hogar_id: string
          id?: string
          invitado_por?: string | null
          respondida_en?: string | null
          token_hash: string
          updated_at?: string
        }
        Update: {
          correo_invitado?: string
          created_at?: string
          estado?: string
          expira_en?: string
          hogar_id?: string
          id?: string
          invitado_por?: string | null
          respondida_en?: string | null
          token_hash?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "invitaciones_hogar_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: false
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "invitaciones_hogar_invitado_por_fkey"
            columns: ["invitado_por"]
            isOneToOne: false
            referencedRelation: "usuarios"
            referencedColumns: ["id"]
          },
        ]
      }
      lecturas: {
        Row: {
          calidad: string
          consumo_kwh: number
          created_at: string
          fecha_hora: string
          id: string
          sensor_id: string
          updated_at: string
        }
        Insert: {
          calidad: string
          consumo_kwh: number
          created_at?: string
          fecha_hora: string
          id?: string
          sensor_id: string
          updated_at?: string
        }
        Update: {
          calidad?: string
          consumo_kwh?: number
          created_at?: string
          fecha_hora?: string
          id?: string
          sensor_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "lecturas_sensor_id_fkey"
            columns: ["sensor_id"]
            isOneToOne: false
            referencedRelation: "sensores_zona"
            referencedColumns: ["id"]
          },
        ]
      }
      metas_consumo: {
        Row: {
          created_at: string
          estado: string
          fecha_fin: string | null
          fecha_inicio: string
          hogar_id: string
          id: string
          tipo: string
          updated_at: string
          valor_kwh_mensual: number
        }
        Insert: {
          created_at?: string
          estado: string
          fecha_fin?: string | null
          fecha_inicio: string
          hogar_id: string
          id?: string
          tipo: string
          updated_at?: string
          valor_kwh_mensual: number
        }
        Update: {
          created_at?: string
          estado?: string
          fecha_fin?: string | null
          fecha_inicio?: string
          hogar_id?: string
          id?: string
          tipo?: string
          updated_at?: string
          valor_kwh_mensual?: number
        }
        Relationships: [
          {
            foreignKeyName: "metas_consumo_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: false
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
        ]
      }
      perfil_transicion: {
        Row: {
          area_techo_m2: number | null
          created_at: string
          factura_promedio_cop: number | null
          hogar_id: string
          id: string
          presupuesto_cop: number | null
          updated_at: string
          vehiculo_electrico: boolean | null
        }
        Insert: {
          area_techo_m2?: number | null
          created_at?: string
          factura_promedio_cop?: number | null
          hogar_id: string
          id?: string
          presupuesto_cop?: number | null
          updated_at?: string
          vehiculo_electrico?: boolean | null
        }
        Update: {
          area_techo_m2?: number | null
          created_at?: string
          factura_promedio_cop?: number | null
          hogar_id?: string
          id?: string
          presupuesto_cop?: number | null
          updated_at?: string
          vehiculo_electrico?: boolean | null
        }
        Relationships: [
          {
            foreignKeyName: "perfil_transicion_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: true
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
        ]
      }
      perfiles_simulacion: {
        Row: {
          activo: boolean
          base_bano_kwh_dia: number
          base_cocina_kwh_dia: number
          base_cuarto_servicio_kwh_dia: number
          base_dormitorio_kwh_dia: number
          base_garaje_kwh_dia: number
          base_lavanderia_kwh_dia: number
          base_oficina_kwh_dia: number
          base_sala_kwh_dia: number
          base_terraza_kwh_dia: number
          created_at: string
          curva_horaria: Json
          factor_fin_semana: number
          humor_max: number
          humor_min: number
          id: string
          nombre: string
          picos_config: Json
          ruido_config: Json
          updated_at: string
        }
        Insert: {
          activo?: boolean
          base_bano_kwh_dia: number
          base_cocina_kwh_dia: number
          base_cuarto_servicio_kwh_dia: number
          base_dormitorio_kwh_dia: number
          base_garaje_kwh_dia: number
          base_lavanderia_kwh_dia: number
          base_oficina_kwh_dia: number
          base_sala_kwh_dia: number
          base_terraza_kwh_dia: number
          created_at?: string
          curva_horaria: Json
          factor_fin_semana: number
          humor_max: number
          humor_min: number
          id?: string
          nombre: string
          picos_config: Json
          ruido_config: Json
          updated_at?: string
        }
        Update: {
          activo?: boolean
          base_bano_kwh_dia?: number
          base_cocina_kwh_dia?: number
          base_cuarto_servicio_kwh_dia?: number
          base_dormitorio_kwh_dia?: number
          base_garaje_kwh_dia?: number
          base_lavanderia_kwh_dia?: number
          base_oficina_kwh_dia?: number
          base_sala_kwh_dia?: number
          base_terraza_kwh_dia?: number
          created_at?: string
          curva_horaria?: Json
          factor_fin_semana?: number
          humor_max?: number
          humor_min?: number
          id?: string
          nombre?: string
          picos_config?: Json
          ruido_config?: Json
          updated_at?: string
        }
        Relationships: []
      }
      preferencias_usuario: {
        Row: {
          base_comparacion: string
          created_at: string
          notif_consejos: boolean
          notif_consumo: boolean
          updated_at: string
          usuario_id: string
        }
        Insert: {
          base_comparacion?: string
          created_at?: string
          notif_consejos?: boolean
          notif_consumo?: boolean
          updated_at?: string
          usuario_id: string
        }
        Update: {
          base_comparacion?: string
          created_at?: string
          notif_consejos?: boolean
          notif_consumo?: boolean
          updated_at?: string
          usuario_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "preferencias_usuario_usuario_id_fkey"
            columns: ["usuario_id"]
            isOneToOne: true
            referencedRelation: "usuarios"
            referencedColumns: ["id"]
          },
        ]
      }
      sensores_zona: {
        Row: {
          created_at: string
          estado: string
          fuente_principal_id: string
          id: string
          updated_at: string
          zona_id: string
        }
        Insert: {
          created_at?: string
          estado: string
          fuente_principal_id: string
          id?: string
          updated_at?: string
          zona_id: string
        }
        Update: {
          created_at?: string
          estado?: string
          fuente_principal_id?: string
          id?: string
          updated_at?: string
          zona_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "sensores_zona_fuente_principal_id_fkey"
            columns: ["fuente_principal_id"]
            isOneToOne: false
            referencedRelation: "fuentes_principales"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "sensores_zona_zona_id_fkey"
            columns: ["zona_id"]
            isOneToOne: true
            referencedRelation: "zonas"
            referencedColumns: ["id"]
          },
        ]
      }
      tarifas_hogar: {
        Row: {
          cargo_fijo_mensual: number | null
          created_at: string
          hogar_id: string
          id: string
          operador: string | null
          precio_kwh: number
          updated_at: string
          vigente_desde: string
          vigente_hasta: string | null
        }
        Insert: {
          cargo_fijo_mensual?: number | null
          created_at?: string
          hogar_id: string
          id?: string
          operador?: string | null
          precio_kwh: number
          updated_at?: string
          vigente_desde: string
          vigente_hasta?: string | null
        }
        Update: {
          cargo_fijo_mensual?: number | null
          created_at?: string
          hogar_id?: string
          id?: string
          operador?: string | null
          precio_kwh?: number
          updated_at?: string
          vigente_desde?: string
          vigente_hasta?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "tarifas_hogar_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: false
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
        ]
      }
      usuarios: {
        Row: {
          avatar_url: string | null
          created_at: string
          id: string
          nombre_completo: string
          telefono: string | null
          updated_at: string
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          id: string
          nombre_completo: string
          telefono?: string | null
          updated_at?: string
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          id?: string
          nombre_completo?: string
          telefono?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      zonas: {
        Row: {
          created_at: string
          estado: string
          hogar_id: string
          id: string
          nombre: string
          tipo: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          estado: string
          hogar_id: string
          id?: string
          nombre: string
          tipo: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          estado?: string
          hogar_id?: string
          id?: string
          nombre?: string
          tipo?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "zonas_hogar_id_fkey"
            columns: ["hogar_id"]
            isOneToOne: false
            referencedRelation: "hogares"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
