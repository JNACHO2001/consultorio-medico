import { cerrarSesion, cuandoExpireLaSesion, sesion } from "./api.js";
import { aviso, h, ROLES } from "./ui.js";
import { pantallaLogin } from "./vistas/login.js";
import { montarPacientes } from "./vistas/pacientes.js";
import { montarAgenda } from "./vistas/agenda.js";
import { montarMiAgenda, montarAtencion } from "./vistas/medico.js";
import { montarUsuarios } from "./vistas/usuarios.js";
import { montarAuditoria } from "./vistas/auditoria.js";
import { montarRecordatorios } from "./vistas/recordatorios.js";

const raiz = document.getElementById("app");

// Cada ruta declara qué roles pueden verla; el servidor vuelve a validar cada petición.
const RUTAS = {
  agenda: { titulo: "Agenda y citas", roles: ["RECEPCION"], montar: montarAgenda },
  "mi-agenda": { titulo: "Mi agenda", roles: ["MEDICO"], montar: montarMiAgenda },
  atencion: { titulo: "Atención", roles: ["MEDICO"], montar: montarAtencion, oculta: true, padre: "mi-agenda" },
  pacientes: { titulo: "Pacientes", roles: ["RECEPCION", "MEDICO"], montar: montarPacientes },
  recordatorios: { titulo: "Recordatorios", roles: ["RECEPCION", "ADMINISTRADOR"], montar: montarRecordatorios },
  usuarios: { titulo: "Usuarios", roles: ["ADMINISTRADOR"], montar: montarUsuarios },
  auditoria: { titulo: "Bitácora de auditoría", roles: ["ADMINISTRADOR"], montar: montarAuditoria },
};
const INICIO = { RECEPCION: "agenda", MEDICO: "mi-agenda", ADMINISTRADOR: "usuarios" };

let principal = null;
let navegacion = null;
let version = 0;

function rutaActual() {
  const [, nombre = "", ...resto] = window.location.hash.split("/");
  return { nombre, parametros: resto.map(decodeURIComponent) };
}

function pintarEstructura(usuario) {
  navegacion = h("nav", { "aria-label": "Secciones" });
  principal = h("main", { class: "principal", id: "contenido", tabindex: "-1" });
  raiz.replaceChildren(
    h("a", { class: "solo-lector", href: "#contenido" }, "Saltar al contenido"),
    h("div", { class: "estructura" },
      h("aside", { class: "lateral" },
        h("div", { class: "logo" }, "Salud Integral", h("small", {}, "Gestión del consultorio")),
        navegacion,
        h("div", { class: "sesion" },
          h("div", {}, h("b", {}, usuario.nombre_completo), ROLES[usuario.rol]),
          h("button", { class: "btn btn-pequeno", type: "button", onclick: salir }, "Cerrar sesión"))),
      principal)
  );
  navegacion.append(
    ...Object.entries(RUTAS)
      .filter(([, r]) => !r.oculta && r.roles.includes(usuario.rol))
      .map(([nombre, r]) => h("a", { href: `#/${nombre}`, "data-ruta": nombre }, r.titulo))
  );
}

async function mostrar() {
  const actual = sesion.actual();
  if (!actual) return;
  const usuario = actual.usuario;
  let { nombre, parametros } = rutaActual();
  const ruta = RUTAS[nombre];
  if (!ruta || !ruta.roles.includes(usuario.rol)) {
    window.location.hash = `#/${INICIO[usuario.rol]}`;
    return;
  }
  const yo = ++version;
  const activa = ruta.padre || nombre;
  for (const enlace of navegacion.querySelectorAll("a")) {
    if (enlace.dataset.ruta === activa) enlace.setAttribute("aria-current", "page");
    else enlace.removeAttribute("aria-current");
  }
  document.title = `${ruta.titulo} – Salud Integral`;
  principal.replaceChildren(h("p", { class: "cargando" }, "Cargando…"));
  try {
    const contenido = h("div");
    await ruta.montar(contenido, { usuario, parametros });
    if (yo === version) {
      principal.replaceChildren(contenido);
      principal.focus({ preventScroll: true });
    }
  } catch (error) {
    if (yo === version) {
      principal.replaceChildren(h("div", { class: "alerta", role: "alert" }, error.message || "No se pudo cargar la pantalla."));
    }
  }
}

async function salir() {
  await cerrarSesion();
  window.location.hash = "";
  mostrarLogin();
}

function entrar(usuario) {
  pintarEstructura(usuario);
  if (!RUTAS[rutaActual().nombre] || !RUTAS[rutaActual().nombre].roles.includes(usuario.rol)) {
    window.location.hash = `#/${INICIO[usuario.rol]}`;
  } else {
    mostrar();
  }
}

function mostrarLogin() {
  version++;
  pantallaLogin(raiz, entrar);
}

cuandoExpireLaSesion(() => {
  sesion.borrar();
  mostrarLogin();
  aviso("Su sesión terminó. Ingrese de nuevo para continuar.", "error");
});
window.addEventListener("hashchange", mostrar);

if (sesion.actual()) entrar(sesion.actual().usuario);
else mostrarLogin();
