"""Uso: ./run_python.bat tools/validar_con_datos_reales.py

Corre un chequeo de humo (smoke test) contra los datos reales que haya en
data/{año}/ — uno por cada año disponible. No reemplaza a la suite de
tests (que usa dataframes sintéticos y corre siempre, incluso sin datos);
existe porque varios bugs reales de esta sesión NO los detectaron los
tests sintéticos y solo aparecieron contra datos de verdad:

- la cantidad de columnas de condiciones de vivienda cambia de 12 (2019)
  a 4 (2024) — un test sintético que arma el dataframe a mano no
  reproduce ese recorte real si no se acuerda de hacerlo a propósito.
- el formato de archivo cambia de .sav (hasta 2023) a .csv combinado
  (2024 en adelante) — dos loaders distintos, cada uno con su propia
  forma de romperse.
- funciones que necesitan la base **nacional** completa (departamento,
  19 categorías) en vez de la base filtrada a Montevideo — fácil de
  confundir, y un dataframe sintético de prueba no distingue una de otra
  si no se arma con cuidado.

No se listan las 42 métricas del catálogo una por una — esa lista cambia
seguido y mantenerla sincronizada acá sería el mismo tipo de
comentario/lista que se desactualiza solo. En cambio, se invoca la
función de `analysis.py` que sostiene cada una contra datos reales
(muchas métricas comparten la misma función genérica con distinto
argumento de agrupación, así que son bastantes menos de 47 llamadas) y se
verifican invariantes genéricos (porcentajes entre 0 y 100, categorías
mutuamente excluyentes sumando ~100%, sin valores nulos donde no
corresponde) — no solo que el pipeline cargue sin explotar. Antes de esta
versión, 31 de las 47 métricas de entonces no tenían ninguna función real
invocada acá, y esa brecha no la detectaba ni la suite sintética ni "no tira
error": números mal calculados podían pasar sin que nada lo notara.
`test_verificacion_catalogo.py::test_toda_metrica_del_manifiesto_tiene_su_funcion_validada_con_datos_reales`
falla si en el futuro se agrega una métrica nueva al catálogo cuya
función no se ejercita en este archivo.

Si hay datos de FIES/Empleo/Seguridad para el año, también se ejercitan.
Si una columna específica de un año no está disponible (ej. situación
ocupacional en 2025), se avisa explícitamente que esa parte no se pudo
verificar en vez de saltearla en silencio.

Si no hay ningún año en data/, termina con un aviso claro en vez de
fallar — no es un error, es el estado normal de un clone limpio.

**Una corrida reporta TODAS las fallas, no solo la primera.** Antes esto
usaba `assert` sueltos, así que la primera falla abortaba todo: al cargar
un año nuevo eso obligaba a un ciclo de corregir → volver a correr →
descubrir la siguiente, un problema por corrida y varios minutos cada
una. Con los datos de 2023 hicieron falta cuatro corridas completas para
descubrir cuatro problemas que ya estaban todos ahí desde la primera. Los
`assert` siguen igual (son la forma más clara de escribir cada chequeo),
pero ahora cada bloque corre dentro de `Recolector.bloque()`, que anota la
falla y sigue. Al final se imprime la lista completa y el script sale con
código 1 si hubo alguna.

Los bloques que dependen de otro que falló se marcan como OMITIDOS y no
como fallas, para que el informe final no se llene de consecuencias de un
mismo problema. FIES, Empleo y Seguridad son fuentes de datos separadas y
se revisan siempre, incluso si todo lo demás falló — es justo donde más
suele cambiar el formato del INE de un año a otro.
"""

import json
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import nbformat  # noqa: E402
import pandas as pd  # noqa: E402
from nbclient import NotebookClient  # noqa: E402
from nbclient.exceptions import CellExecutionError  # noqa: E402

from encuesta_hogares import (  # noqa: E402
    analysis,
    config,
    data_loader,
    notebook_builder,
    preprocessing,
    verificacion_catalogo,
    verificacion_notebook,
    verificacion_plausibilidad,
    visualization,
)


class _Omitido(Exception):
    """Un bloque no se pudo correr porque algo de lo que depende falló
    antes. No es una falla nueva — es una consecuencia de otra."""


class Recolector:
    """Junta todas las fallas de una corrida en vez de cortar en la primera.

    Nace del problema de fondo que tenía este script: usaba `assert`
    sueltos, así que la primera falla abortaba todo. Al agregar un año
    nuevo eso obligaba a un ciclo de corregir → correr de nuevo →
    descubrir la siguiente → corregir, una falla por corrida. Con los
    datos de 2023 hicieron falta cuatro corridas completas del pipeline
    (varios minutos cada una) para descubrir cuatro problemas que ya
    estaban todos ahí desde la primera.

    Ahora cada bloque se registra y la corrida sigue: una sola pasada
    enumera todo lo que le pasa a un año nuevo. Los bloques que dependen
    de otro que falló se marcan como OMITIDOS y no como fallas, para no
    inflar el informe final con consecuencias de un mismo problema.
    """

    def __init__(self) -> None:
        self.fallas: list[tuple[str, str]] = []
        self.omitidos: list[tuple[str, str]] = []

    @contextmanager
    def bloque(self, etiqueta: str):
        try:
            yield
        except _Omitido as e:
            self.omitidos.append((etiqueta, str(e)))
            print(f"[OMITIDO] {etiqueta} — {e}")
        except Exception as e:
            self.fallas.append((etiqueta, f"{type(e).__name__}: {e}"))
            print(f"[FALLA] {etiqueta} — {type(e).__name__}: {e}")

    @staticmethod
    def requiere(**valores) -> None:
        """Corta el bloque si algo de lo que necesita quedó sin calcular
        por una falla anterior."""
        faltan = [nombre for nombre, valor in valores.items() if valor is None]
        if faltan:
            raise _Omitido(f"depende de {', '.join(faltan)}, que no se pudo calcular")

    def informe_final(self, anios: list[str]) -> int:
        print(f"\n\n{'=' * 60}")
        if not self.fallas:
            print(f"[OK] VALIDACIÓN COMPLETA: {', '.join(anios)}")
            if self.omitidos:
                print(f"({len(self.omitidos)} bloque(s) omitidos por falta de datos de ese año, sin fallas)")
            return 0

        print(f"[FALLÓ] {len(self.fallas)} problema(s) encontrados — la lista completa, no solo el primero:")
        print("=" * 60)
        for etiqueta, detalle in self.fallas:
            print(f"\n  • {etiqueta}\n    {detalle}")
        if self.omitidos:
            print(f"\n{len(self.omitidos)} bloque(s) quedaron sin verificar por depender de los anteriores:")
            for etiqueta, motivo in self.omitidos:
                print(f"  - {etiqueta}: {motivo}")
        print(f"\n{'=' * 60}\nAños revisados: {', '.join(anios)}")
        return 1


def _cargar_hogares_y_personas(anio: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga Hogares/Personas del año, **normalizando el departamento** —
    exactamente lo mismo que hace `notebook_builder.celda_preparacion_datos`
    en el flujo real.

    Esa normalización no estaba acá y el resultado fue que esta validación
    dejó de reflejar la producción: al sumarle el componente de empleo al
    índice territorial (v0.10.0), el cruce por departamento daba 0 filas
    solo en este script —porque acá `hogares` venía con "Montevideo" y el
    empleo normalizado con "MONTEVIDEO"—, mientras el notebook real
    funcionaba bien. Una validación que no reproduce el mismo preprocesado
    que producción sirve para muy poco.
    """
    carpeta = config.DATA_DIR / anio
    if config.hogares_csv_file(anio).exists():
        hogares, personas = data_loader.load_hogares_personas_csv(anio)
    else:
        hogares = data_loader.load_hogares(sorted(carpeta.glob("H_*.sav"))[0])
        personas = data_loader.load_personas(sorted(carpeta.glob("P_*.sav"))[0])
    return preprocessing.normalizar_departamento(hogares), personas


def _revisar_plausibilidad(anio: str, bloque: str, cifras: dict) -> None:
    """Frena si una cifra es un disparate o rompe una identidad estadística.

    No compara contra las cifras del INE ni pretende reproducirlas: la
    metodología de este proyecto puede diferir legítimamente. Lo que
    verifica es que el resultado no sea imposible — ver
    `verificacion_plausibilidad`.
    """
    limpias = {k: v for k, v in cifras.items() if isinstance(v, (int, float))}
    hallazgos = verificacion_plausibilidad.revisar(limpias)
    detalle = "\n  ".join(str(h) for h in hallazgos)
    assert not hallazgos, f"{anio} · {bloque}: el resultado no es plausible —\n  {detalle}"


def validar_anio(anio: str, rec: Recolector) -> None:
    print(f"\n{'=' * 60}\nAÑO {anio}\n{'=' * 60}")

    # Se inicializan en None para que un bloque que falle no deje a los
    # siguientes con un NameError (que se registraría como una falla
    # nueva, tapando la de verdad): `rec.requiere(...)` los revisa y marca
    # el bloque dependiente como OMITIDO en vez de FALLA.
    hogares = personas = hogares_cond = None
    hogares_mdeo = hogares_ext = tipo_hogar = None
    n_carencias = None

    with rec.bloque(f"{anio} · Carga de Hogares/Personas"):
        hogares, personas = _cargar_hogares_y_personas(anio)
        print(f"Hogares (nacional): {len(hogares)} — departamentos: {hogares['departamento'].nunique()}")
        assert hogares["departamento"].nunique() > 1, "se esperaban varios departamentos en la base nacional"

    # --- Vivienda: la cantidad de carencias cambia de año a año, y algunos
    # años (2023, verificado contra los datos reales) no tienen ninguna -
    # el módulo C5 completo no se relevó ese año. analysis.py ya convierte
    # eso en un ValueError explícito (ver
    # analysis._condiciones_vivienda_disponibles) en vez de devolver un
    # "0% con carencia" que parecería un cálculo real y no lo es - acá se
    # respeta esa señal en vez de forzar el cálculo.
    with rec.bloque(f"{anio} · Vivienda (precariedad estructural)"):
        rec.requiere(hogares=hogares)
        hogares_cond = preprocessing.decode_condiciones_vivienda(hogares)
        n_carencias = sum(1 for c in config.CONDICIONES_VIVIENDA_COLUMNS.values() if c in hogares_cond.columns)
        print(f"Carencias de vivienda disponibles: {n_carencias}")
        if n_carencias > 0:
            resultado = analysis.precariedad_estructural(hogares_cond)
            assert 0 <= resultado["pct_con_carencia"] <= 100
            assert visualization.plot_precariedad_estructural(resultado) is not None
        else:
            print("Precariedad estructural: sin verificar — módulo de condiciones de vivienda no disponible este año")

    # --- Territorio: índice compuesto sobre la base nacional (no Montevideo).
    # El dueño del proyecto eligió "avisar explícitamente que un año sin
    # vivienda no da un componente de precariedad" sobre "recalcular el
    # índice completo con menos columnas". No eligió entre marcar el
    # índice territorial entero como no disponible ese año o recalcularlo
    # solo con pobreza+estrato (quedó abierto) - se optó acá por lo más
    # conservador (marcarlo entero) para no mezclar, bajo el mismo nombre
    # de métrica, un índice de 3 componentes con uno de 2 sin que se note.
    with rec.bloque(f"{anio} · Índice de desarrollo territorial"):
        rec.requiere(hogares=hogares, hogares_cond=hogares_cond)
        hogares_cond["pobre"] = hogares_cond["pobre"] == 1.0
        hay_empleo = config.datos_disponibles(anio)["empleo"]
        if n_carencias > 0 and hay_empleo:
            pobreza_depto = analysis.pct_pobres_por(hogares_cond, "departamento").set_index("departamento")
            estrato_depto = analysis.estrato_promedio_por(hogares, "departamento").set_index("departamento")
            precariedad_depto = analysis.precariedad_estructural_por(hogares_cond, "departamento").set_index("departamento")
            # normalizar_departamento sobre Empleo no es opcional: esos
            # archivos traen "Artigas" y los de Hogares "ARTIGAS".
            # Verificado contra 2025: sin normalizar coinciden 0 de 19
            # departamentos y el dropna() deja el índice vacío en silencio.
            empleo_territorial = preprocessing.normalizar_departamento(
                preprocessing.prepare_empleo(data_loader.load_empleo(anio))
            )
            empleo_depto = analysis.tasas_actividad_empleo_desempleo_por(
                empleo_territorial, "departamento"
            ).set_index("departamento")
            componentes = pd.DataFrame({
                "Pobreza": pobreza_depto["pct_pobres"],
                "Precariedad de vivienda": precariedad_depto["pct_precariedad"],
                "Empleo": empleo_depto["tasa_empleo"],
                "Nivel económico": estrato_depto["estrato_promedio"],
            }).dropna()
            assert len(componentes) > 1, (
                f"el índice territorial quedó con {len(componentes)} departamento(s) — "
                "el cruce por departamento no coincidió entre fuentes"
            )
            indice = analysis.indice_desarrollo_territorial(
                componentes, invertir=["Pobreza", "Precariedad de vivienda"]
            )
            assert indice["indice"].between(0, 1).all()
            assert visualization.plot_indice_desarrollo_territorial(indice) is not None
            assert visualization.plot_perfil_territorial(indice) is not None
            print(f"Índice territorial: OK ({len(indice)} departamentos, 4 componentes)")
        elif n_carencias == 0:
            print("Índice territorial: sin verificar — módulo de condiciones de vivienda no disponible este año")
        else:
            print("Índice territorial: sin verificar — sin datos de Empleo, uno de sus 4 componentes")

    # --- Brecha Digital / Hogares: filtro a Montevideo + variables decodificadas ---
    with rec.bloque(f"{anio} · Brecha digital y pobreza (Montevideo)"):
        rec.requiere(hogares=hogares)
        hogares_mdeo = preprocessing.prepare_hogares_montevideo(hogares)
        hogares_ext = preprocessing.prepare_hogares_extendido(hogares_mdeo)
        resumen_conectividad = analysis.resumen_conectividad(hogares_ext)
        assert resumen_conectividad.total_hogares > 0
        assert 0 <= resumen_conectividad.pct_con_internet <= 100
        _revisar_plausibilidad(anio, "Conectividad", {
            "pct_con_internet": resumen_conectividad.pct_con_internet,
        })
        print(f"Montevideo: {resumen_conectividad.total_hogares} hogares, {resumen_conectividad.pct_con_internet}% con internet (ponderado)")

        pobres = analysis.pct_pobres_indigentes(hogares_ext)
        assert 0 <= pobres["pct_pobres"] <= 100
        _revisar_plausibilidad(anio, "Pobreza", pobres)
        print(f"Pobreza (ponderada): {pobres['pct_pobres']}% — sin ponderar sería {round(hogares_ext['pobre'].mean() * 100, 2)}%")

        brecha = analysis.brecha_digital_por_nivel_economico(hogares_ext)
        assert visualization.plot_brecha_digital(brecha) is not None

        # --- Métrica 3: sin función de análisis propia hasta la corrida que agregó este manifiesto ---
        hogares_ext["calidad_conexion"] = preprocessing.clasificar_calidad_conexion(hogares_ext)
        calidad = analysis.calidad_conexion_por(hogares_ext, "nivel_economico")
        assert calidad.sum(axis=1).round(0).between(99, 101).all()
        assert visualization.plot_calidad_conexion_por(calidad, "nivel económico") is not None
        print("Calidad de conexión por nivel económico: OK (ponderado)")

    # --- Hogares: composición vía Personas, requiere el merge completo ---
    with rec.bloque(f"{anio} · Composición de hogares"):
        rec.requiere(hogares=hogares, personas=personas)
        tipo_hogar = preprocessing.clasificar_tipo_hogar(personas, hogares)
        resumen_tipos = analysis.tipos_hogar_resumen(tipo_hogar)
        assert abs(resumen_tipos["pct_hogares"].sum() - 100.0) < 0.5
        jefatura = analysis.tasa_jefatura_femenina(tipo_hogar)
        assert 0 <= jefatura["pct_jefatura_femenina"] <= 100
        print(f"Tipos de hogar: OK ({len(resumen_tipos)} categorías) — jefatura femenina: {jefatura['pct_jefatura_femenina']}%")

        unipersonales_mayores = analysis.pct_unipersonales_mayores(tipo_hogar)
        assert 0 <= unipersonales_mayores["pct_unipersonales_mayores"] <= 100

        cat_a, cat_b = resumen_tipos["tipo_hogar"].iloc[0], resumen_tipos["tipo_hogar"].iloc[-1]
        diferencia_tipos = analysis.diferencia_entre_categorias(resumen_tipos, "tipo_hogar", cat_a, cat_b, "pct_hogares")
        assert -100 <= diferencia_tipos <= 100
        print("Unipersonales mayores / diferencia entre tipos de hogar: OK")

    with rec.bloque(f"{anio} · Carencias de vivienda más frecuentes"):
        rec.requiere(hogares_cond=hogares_cond)
        if n_carencias > 0:
            carencias_frecuentes = analysis.carencias_estructurales_mas_frecuentes(hogares_cond)
            assert carencias_frecuentes["pct_hogares"].between(0, 100).all() and len(carencias_frecuentes) == n_carencias
            print("Carencias más frecuentes: OK")
        else:
            print("Carencias más frecuentes: sin verificar — módulo de vivienda no disponible este año")

    # --- Brecha Digital por cohorte/jefatura/índice de acceso, Hacinamiento,
    # Razón de dependencia: necesitan columnas derivadas que se arman acá
    # mismo, siguiendo el mismo criterio que ya usa el notebook real.
    with rec.bloque(f"{anio} · Brecha digital por cohorte / jefatura / índice de acceso"):
        rec.requiere(hogares_ext=hogares_ext, tipo_hogar=tipo_hogar)
        hogares_ext_con_jefe = hogares_ext.merge(
            tipo_hogar[["id_hogar", "jefe_sexo", "jefe_edad"]], on="id_hogar", how="left"
        )
        hogares_ext_con_jefe["cohorte"] = preprocessing.compute_cohorte_generacional(hogares_ext_con_jefe, int(anio))
        hogares_ext_con_jefe["indice_acceso_digital"] = preprocessing.compute_indice_acceso_digital(hogares_ext_con_jefe)

        brecha_cohorte = analysis.brecha_digital_por_cohorte(hogares_ext_con_jefe)
        assert brecha_cohorte["pct_penetracion"].between(0, 100).all()
        brecha_jefatura = analysis.brecha_digital_por_jefatura(hogares_ext_con_jefe)
        assert brecha_jefatura["pct_penetracion"].between(0, 100).all()
        indice_por_nivel = analysis.indice_acceso_digital_por(hogares_ext_con_jefe, "nivel_economico")
        assert indice_por_nivel["indice_promedio"].between(0, 3).all()
        if "tiene_tablet_ibirapita" in hogares_ext_con_jefe.columns:
            tablet_por_nivel = analysis.adopcion_tablet_ibirapita_por(hogares_ext_con_jefe, "nivel_economico")
            assert tablet_por_nivel["pct_con_tablet"].between(0, 100).all()
        print("Brecha digital por cohorte / jefatura / índice de acceso digital: OK (ponderado)")

    with rec.bloque(f"{anio} · Hacinamiento"):
        rec.requiere(hogares_mdeo=hogares_mdeo)
        hogares_mdeo_hacinamiento = preprocessing.compute_hacinamiento(hogares_mdeo)
        hacinamiento_por_nivel = analysis.pct_hacinamiento_por(hogares_mdeo_hacinamiento, "nivel_economico")
        assert hacinamiento_por_nivel["pct_hacinamiento"].between(0, 100).all()
        print("Hacinamiento por nivel económico: OK")

    with rec.bloque(f"{anio} · Razón de dependencia demográfica"):
        rec.requiere(hogares=hogares, personas=personas)
        personas_con_depto = preprocessing.merge_personas(hogares, personas)
        dependencia_por_depto = analysis.razon_dependencia_por(personas_con_depto, "departamento")
        assert dependencia_por_depto["razon_dependencia"].dropna().ge(0).all()
        print(f"Razón de dependencia demográfica por departamento: OK ({len(dependencia_por_depto)} departamentos)")

    # FIES, Empleo y Seguridad son fuentes de datos separadas: no dependen
    # de nada de lo anterior, así que se revisan siempre — incluso si todo
    # lo de arriba falló. Es justo donde más suele cambiar el INE de un año
    # a otro, y donde más importa enterarse en la misma corrida.
    disponibles = config.datos_disponibles(anio)
    print(f"Datos opcionales disponibles: {disponibles}")

    if disponibles["fies"]:
        _validar_fies(anio, rec)

    if disponibles["empleo"]:
        _validar_empleo(anio, rec)

    if disponibles["seguridad"]:
        _validar_seguridad(anio, rec)

    fallas_del_anio = [e for e, _ in rec.fallas if e.startswith(f"{anio} ·")]
    if not fallas_del_anio:
        print(f"\n[OK] Año {anio}: validación completa sin errores")
    else:
        print(f"\n[FALLÓ] Año {anio}: {len(fallas_del_anio)} problema(s) — se sigue con el resto igual")


def _validar_fies(anio: str, rec: Recolector) -> None:
    with rec.bloque(f"{anio} · FIES (seguridad alimentaria)"):
        fies = data_loader.load_fies(config.fies_file(anio))
        fies_clasificado = preprocessing.prepare_fies(fies)
        prevalencia = analysis.prevalencia_inseguridad_alimentaria(fies_clasificado)
        assert 0 <= prevalencia["moderada_o_severa"] <= 100
        _revisar_plausibilidad(anio, "FIES", {
            "pct_inseguridad_alimentaria": prevalencia["moderada_o_severa"],
            "pct_inseguridad_severa": prevalencia.get("severa"),
        })
        print(f"FIES: OK (inseguridad moderada o severa: {prevalencia['moderada_o_severa']}%)")

        inseguridad_por_region = analysis.inseguridad_alimentaria_por(fies_clasificado, "region")
        assert inseguridad_por_region["pct_inseguridad"].between(0, 100).all()
        print(f"FIES por región: OK ({len(inseguridad_por_region)} regiones)")


def _validar_empleo(anio: str, rec: Recolector) -> None:
    with rec.bloque(f"{anio} · Empleo"):
        empleo = preprocessing.prepare_empleo(data_loader.load_empleo(anio))
        assert empleo["mes"].nunique() == 12, "el panel de empleo tiene que traer los 12 meses"
        tasas = analysis.tasas_actividad_empleo_desempleo(empleo)
        assert 0 <= tasas["tasa_desempleo"] <= 100
        _revisar_plausibilidad(anio, "Empleo", tasas)
        print(f"Empleo: OK (tasa de desempleo promedio anual: {tasas['tasa_desempleo']}%)")

        tasas_por_sexo = analysis.tasas_actividad_empleo_desempleo_por(empleo, "sexo_grupo")
        assert tasas_por_sexo[["tasa_actividad", "tasa_empleo", "tasa_desempleo"]].apply(
            lambda s: s.between(0, 100)
        ).all().all()
        sexos = tasas_por_sexo["sexo_grupo"].tolist()
        if len(sexos) >= 2:
            brecha_genero = analysis.brecha_por_grupo(tasas_por_sexo, "sexo_grupo", sexos[0], sexos[1])
            assert brecha_genero.abs().le(100).all()
        print("Empleo por sexo / brecha de género: OK")

        ocupados = empleo[empleo["condicion_actividad"] == "Ocupados"]
        if "es_informal" in ocupados.columns:
            informalidad_por_sexo = analysis.tasa_mensual_promedio_por(ocupados, "sexo_grupo", "es_informal")
            assert informalidad_por_sexo["pct_promedio"].between(0, 100).all()
            print("Informalidad por sexo: OK")
        else:
            print("Informalidad por sexo: sin verificar — 'es_informal' no está disponible este año")

        columna_sector = next((c for c in ("sit_ocup", "situacion_ocupacional") if c in ocupados.columns), None)
        if columna_sector:
            composicion_sector = analysis.composicion_categorica_por_mes_promedio(ocupados, "sexo_grupo", columna_sector)
            assert composicion_sector.sum(axis=1).round(0).between(99, 101).all()
            print("Situación ocupacional por sector y sexo: OK")
        else:
            print("Situación ocupacional por sector y sexo: sin verificar — columna no disponible este año")


def _validar_seguridad(anio: str, rec: Recolector) -> None:
    with rec.bloque(f"{anio} · Seguridad y victimización"):
        victimizacion = data_loader.load_victimizacion(anio)
        largo = preprocessing.melt_delitos(preprocessing.prepare_victimizacion(victimizacion))
        assert len(largo) > 0
        print(f"Seguridad/Victimización: OK ({len(largo)} filas tipo_delito x persona)")

        victimizados = largo[largo["victimizado"]]
        comunicacion_por_delito = analysis.pct_ponderado_por(
            victimizados, "tipo_delito", "comunicacion_policia", "ponderador_victimizacion"
        )
        assert comunicacion_por_delito["pct"].between(0, 100).all()
        denuncia_por_delito = analysis.pct_ponderado_por(
            victimizados, "tipo_delito", "denuncia_formal", "ponderador_victimizacion"
        )
        assert denuncia_por_delito["pct"].between(0, 100).all()
        diferencia_comunicacion_denuncia = analysis.diferencia_entre_tablas(
            comunicacion_por_delito, denuncia_por_delito, "tipo_delito", "pct"
        )
        assert diferencia_comunicacion_denuncia.abs().le(100).all()
        print(f"Comunicación a la policía vs. denuncia formal, por tipo de delito: OK ({len(comunicacion_por_delito)} tipos)")


def validar_notebook_builder(anio: str, rec: Recolector) -> None:
    """Corre DE VERDAD el código que genera `notebook_builder.py` para
    todas las métricas del catálogo disponibles este año (no una
    reimplementación a mano de la misma lógica, como el resto de este
    archivo) — así, si una plantilla queda desincronizada de
    `analysis.py`/`visualization.py` (un parámetro renombrado, una
    función que ya no existe), esto revienta acá, en un chequeo que ya es
    parte del flujo esperado antes de publicar, no en un informe real de
    un usuario.

    Nace de la misma revisión que agregó `notebook_builder.py`: con solo
    un test de que "cada número del catálogo tiene una función" (ver
    `test_notebook_builder.py`) no alcanza — ese test no ejecuta nada
    contra datos reales, y un año concreto le faltaba una columna que
    otro sí tenía (ver SIT_OCUP/SECTOR_F más abajo). Solo cubre el año
    base — la comparación entre años quedó en código libre (ver el
    docstring de notebook_builder.py), no hay una plantilla que probar
    para eso acá.
    """
    print(f"\n--- notebook_builder: ejecutando las plantillas del catálogo para {anio} ---")
    with rec.bloque(f"{anio} · notebook_builder (plantillas del catálogo)"):
        _correr_plantillas_del_catalogo(anio)


def _correr_plantillas_del_catalogo(anio: str) -> None:
    disponibles = config.datos_disponibles(anio)
    catalogo = verificacion_catalogo.numeros_del_catalogo()
    no_disponibles_empleo = set(verificacion_catalogo.metricas_empleo_no_disponibles(anio))
    no_disponibles_hogares = set(verificacion_catalogo.metricas_hogares_no_disponibles(anio))
    metricas = sorted(n for n in catalogo if n not in no_disponibles_empleo | no_disponibles_hogares)
    if not disponibles["fies"]:
        metricas = [n for n in metricas if n not in range(21, 28)]
    if not disponibles["empleo"]:
        # 13-15 (Territorio) tambien: desde la 0.10.0 el indice de
        # desarrollo territorial lleva la tasa de empleo como uno de sus
        # cuatro componentes, asi que sin datos de Empleo no se puede
        # calcular (el caso real es 2019, que no tiene ese modulo).
        metricas = [n for n in metricas if n not in range(28, 36) and n not in (13, 14, 15)]
    if not disponibles["seguridad"]:
        metricas = [n for n in metricas if n not in range(36, 43)]

    celdas = notebook_builder.construir_celdas_notebook(
        anio_base=int(anio),
        metricas=metricas,
        incluir_brecha_digital=True,
        incluir_fies=disponibles["fies"],
        incluir_empleo=disponibles["empleo"],
        incluir_seguridad=disponibles["seguridad"],
    )

    # Se ejecuta con un kernel de Jupyter de verdad (nbclient), no exec()
    # crudo en este mismo proceso: `fig.show()` de Plotly depende de los
    # hooks de display de IPython para renderizar — fuera de un kernel
    # real, cae a un camino distinto (print de HTML crudo a la consola)
    # que no es el que corre en un notebook real y que además puede
    # fallar por la codificación de la consola sin que sea un error de
    # verdad de la plantilla.
    ruta_tmp = config.PROJECT_ROOT / "notebooks" / f"_validacion_notebook_builder_{anio}.ipynb"
    # Con la celda de cifras al final, igual que lo arma generar_informe.construir.
    celdas.append(notebook_builder.celda_cifras(ruta_tmp))
    notebook_builder.escribir_notebook(celdas, ruta_tmp)
    nb = nbformat.read(str(ruta_tmp), as_version=4)
    ruta_cifras = notebook_builder.ruta_cifras(ruta_tmp)
    try:
        # Las mismas verificaciones que corre el pipeline, sobre el notebook
        # real construido y sobre el real ejecutado: es el único lugar donde
        # los guardianes se enfrentan a outputs de verdad (imágenes PNG,
        # prints) y no a dicts sintéticos.
        problemas = verificacion_notebook.verificar_antes_de_ejecutar(json.loads(ruta_tmp.read_text(encoding="utf-8")))
        assert not problemas, f"el notebook construido para {anio} no pasa la verificación previa: {problemas}"
        NotebookClient(nb, timeout=180, kernel_name="python3").execute()
        nbformat.write(nb, str(ruta_tmp))
        problemas = verificacion_notebook.verificar_despues_de_ejecutar(json.loads(ruta_tmp.read_text(encoding="utf-8")))
        assert not problemas, f"el notebook ejecutado para {anio} tiene problemas: {problemas}"
        assert ruta_cifras.exists(), f"la celda de cifras no escribió {ruta_cifras.name}"
        cifras = json.loads(ruta_cifras.read_text(encoding="utf-8"))
        assert len(cifras) >= len(metricas) // 2, f"la celda de cifras dejó solo {len(cifras)} variables para {len(metricas)} métricas"
        numeros = verificacion_notebook.numeros_de_cifras(cifras)
        assert numeros, "la celda de cifras no dejó ningún número"
    except CellExecutionError as e:
        raise AssertionError(f"notebook_builder rompió ejecutando el notebook de prueba para {anio}: {e}") from e
    finally:
        ruta_tmp.unlink(missing_ok=True)
        ruta_cifras.unlink(missing_ok=True)
        Path(str(ruta_tmp).replace(".ipynb", " (anterior).ipynb")).unlink(missing_ok=True)

    print(f"[OK] {len(metricas)} métricas del catálogo, plantillas ejecutadas sin error ({len(celdas)} celdas), "
          f"verificaciones previa y posterior en verde, {len(cifras)} variables de cifras")


def main() -> int:
    anios = sorted(p.name for p in config.DATA_DIR.iterdir() if p.is_dir() and p.name.isdigit()) if config.DATA_DIR.exists() else []
    anios = [a for a in anios if list((config.DATA_DIR / a).glob("H_*.sav")) or config.hogares_csv_file(a).exists()]

    if not anios:
        print("No hay datos en data/ todavía — no es un error, es el estado normal de un clone limpio.")
        print("Este script solo tiene sentido correrlo una vez que haya al menos un año descargado.")
        return 0

    rec = Recolector()

    for anio in anios:
        validar_anio(anio, rec)

    for anio in anios:
        validar_notebook_builder(anio, rec)

    return rec.informe_final(anios)


if __name__ == "__main__":
    sys.exit(main())
