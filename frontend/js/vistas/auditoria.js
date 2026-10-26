import { api } from "../api.js";
import { alerta, campo, entrada, fechaHora, h, seleccion } from "../ui.js";

const ACCIONES = ["CREACION", "LECTURA", "LECTURA_MULTIPLE", "BUSQUEDA", "LISTADO", "MODIFICACION", "NOTA_ACLARATORIA", "DESACTIVACION", "INICIO_SESION", "INICIO_SESION_FALLIDO", "CIERRE_SESION"];
const ENTIDADES = ["Paciente", "Consulta", "HistoriaClinica", "Usuario", "Sesion"];
const NOMBRES = {
  CREACION: "Creación", LECTURA: "Lectura", LECTURA_MULTIPLE: "Lectura de varios registros", BUSQUEDA: "Búsqueda", LISTADO: "Listado",
  MODIFICACION: "Modificación", NOTA_ACLARATORIA: "Nota aclaratoria", DESACTIVACION: "Desactivación", INICIO_SESION: "Inicio de sesión",
  INICIO_SESION_FALLIDO: "Inicio de sesión fallido", CIERRE_SESION: "Cierre de sesión",
};
const nombre = (codigo) => NOMBRES[codigo] || codigo;

export async function montarAuditoria(raiz) {
  const zona = h("div", { "aria-live": "polite" });
  const usuario = entrada("usuario", { placeholder: "Todos" });
  const accion = seleccion("accion", [["", "Todas"], ...ACCIONES.map((a) => [a, nombre(a)])]);
  const entidad = seleccion("entidad", [["", "Todas"], ...ENTIDADES.map((e) => [e, e === "HistoriaClinica" ? "Historia clínica" : e === "Sesion" ? "Sesión" : e])]);

  async function cargar(e) {
    e?.preventDefault();
    zona.replaceChildren(h("p", { class: "cargando" }, "Consultando…"));
    try {
      const filas = await api.get("/api/auditoria", { usuario: usuario.value.trim(), accion: accion.value, entidad: entidad.value, limite: 300 });
      zona.replaceChildren(filas.length
        ? h("div", { class: "tabla-contenedor" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Fecha y hora", "Usuario", "Acción", "Sobre"].map((t) => h("th", {}, t)), h("th", { class: "num" }, "Registro"))),
          h("tbody", {}, filas.map((f) => h("tr", {},
            h("td", { class: "fecha" }, fechaHora(f.fecha_hora)), h("td", {}, f.usuario || "—"), h("td", {}, nombre(f.accion)),
            h("td", {}, f.entidad === "HistoriaClinica" ? "Historia clínica" : f.entidad === "Sesion" ? "Sesión" : f.entidad), h("td", { class: "num" }, f.id_entidad || "—"))))))
        : h("div", { class: "vacio" }, "No hay registros con esos filtros."));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  raiz.append(
    h("header", { class: "encabezado" }, h("div", {}, h("h1", {}, "Bitácora de auditoría"),
      h("p", {}, "Quién consultó o modificó información de pacientes y cuándo. Los registros no se pueden editar ni borrar."))),
    h("section", { class: "panel" },
      h("form", { class: "barra", onsubmit: cargar }, campo("Usuario", usuario), campo("Acción", accion), campo("Sobre", entidad),
        h("button", { class: "btn btn-primario", type: "submit" }, "Filtrar")),
      zona));
  await cargar();
}
