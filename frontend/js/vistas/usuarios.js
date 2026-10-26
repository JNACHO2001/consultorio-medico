import { api } from "../api.js";
import { abrirDialogo, alerta, aviso, campo, confirmar, datosDe, entrada, h, ROLES, seleccion } from "../ui.js";

export async function montarUsuarios(raiz, { usuario }) {
  const zona = h("div");

  async function cargar() {
    try {
      const usuarios = await api.get("/api/usuarios");
      zona.replaceChildren(h("div", { class: "tabla-contenedor" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Nombre", "Usuario", "Rol", "Especialidad", "Estado", ""].map((t) => h("th", {}, t)))),
        h("tbody", {}, usuarios.map((u) => h("tr", {},
          h("td", {}, h("b", {}, u.nombre_completo)), h("td", {}, u.nombre_usuario), h("td", {}, ROLES[u.rol]),
          h("td", {}, u.especialidad || "—"),
          h("td", {}, h("span", { class: `sello ${u.activo ? "atendida" : "cancelada"}` }, u.activo ? "Activo" : "Inactivo")),
          h("td", {}, u.activo && u.id !== usuario.id
            ? h("button", { class: "btn btn-peligro btn-pequeno", type: "button", onclick: () => desactivar(u) }, "Desactivar") : null)))))));
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  async function desactivar(u) {
    const ok = await confirmar({
      titulo: "Desactivar usuario",
      mensaje: `${u.nombre_completo} ya no podrá iniciar sesión. Su historial de acciones se conserva en la bitácora.`,
      textoConfirmar: "Desactivar", peligro: true,
    });
    if (!ok) return;
    try {
      await api.post(`/api/usuarios/${u.id}/desactivar`);
      aviso("Usuario desactivado.");
      cargar();
    } catch (error) {
      aviso(error.message, "error");
    }
  }

  function nuevo() {
    abrirDialogo({
      titulo: "Crear usuario",
      construir: (cuerpo, cerrar) => {
        const mensaje = h("div");
        const rol = seleccion("rol", [["RECEPCION", "Recepción"], ["MEDICO", "Médico"], ["ADMINISTRADOR", "Administrador"]], "RECEPCION");
        const medico = h("div", { hidden: true },
          campo("Especialidad", entrada("especialidad")), campo("Registro médico", entrada("registro_medico")));
        rol.addEventListener("change", () => { medico.hidden = rol.value !== "MEDICO"; });
        const guardar = h("button", { class: "btn btn-primario", type: "submit" }, "Crear usuario");
        const form = h("form", {
          onsubmit: async (e) => {
            e.preventDefault();
            guardar.disabled = true;
            const datos = datosDe(form);
            datos.contrasena = form.elements.contrasena.value;
            try {
              await api.post("/api/usuarios", datos);
              cerrar();
              aviso("Usuario creado.");
              cargar();
            } catch (error) {
              mensaje.replaceChildren(alerta(error));
              guardar.disabled = false;
            }
          },
        }, mensaje,
          campo("Nombre completo", entrada("nombre_completo", { requerido: true })),
          campo("Usuario", entrada("nombre_usuario", { requerido: true, autocomplete: "off" })),
          campo("Contraseña", entrada("contrasena", { tipo: "password", requerido: true, autocomplete: "new-password" }), "Mínimo 8 caracteres, con letras y números."),
          campo("Rol", rol), medico,
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
        cuerpo.append(form);
      },
    });
  }

  raiz.append(
    h("header", { class: "encabezado" },
      h("div", {}, h("h1", {}, "Usuarios"), h("p", {}, "Cada persona entra con su propio usuario y solo ve lo que su rol permite.")),
      h("button", { class: "btn btn-primario", type: "button", onclick: nuevo }, "Crear usuario")),
    h("section", { class: "panel" }, zona));
  await cargar();
}
