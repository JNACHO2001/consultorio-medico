import { iniciarSesion } from "../api.js";
import { alerta, campo, entrada, h } from "../ui.js";

const DEMO = [
  ["recepcion1", "Recepción"],
  ["dr.perez", "Médico (Medicina general)"],
  ["dra.gomez", "Médica"],
  ["admin", "Administrador"],
];

export function pantallaLogin(raiz, alEntrar) {
  const usuario = entrada("usuario", { requerido: true, autocomplete: "username", autofocus: true });
  const clave = entrada("contrasena", { tipo: "password", requerido: true, autocomplete: "current-password" });
  const mensaje = h("div", { "aria-live": "polite" });
  const enviar = h("button", { class: "btn btn-primario", type: "submit" }, "Entrar");

  const formulario = h("form", {
    onsubmit: async (e) => {
      e.preventDefault();
      mensaje.replaceChildren();
      enviar.disabled = true;
      try {
        const u = await iniciarSesion(usuario.value.trim(), clave.value);
        alEntrar(u);
      } catch (error) {
        mensaje.replaceChildren(alerta(error));
        clave.value = "";
        clave.focus();
      } finally {
        enviar.disabled = false;
      }
    },
  },
    h("h2", {}, "Ingreso del personal"),
    mensaje,
    campo("Usuario", usuario),
    campo("Contraseña", clave),
    h("div", { class: "acciones" }, enviar),
    h("details", { class: "demo" },
      h("summary", {}, "Usuarios de demostración"),
      h("p", { class: "suave pequeno" }, "Contraseña de todos: Salud2026*"),
      h("ul", {}, DEMO.map(([nombre, rol]) =>
        h("li", {}, h("button", {
          type: "button",
          onclick: () => {
            usuario.value = nombre;
            clave.value = "Salud2026*";
            enviar.focus();
          },
        }, h("b", {}, nombre), rol))))
    )
  );

  raiz.replaceChildren(
    h("main", { class: "acceso" },
      h("section", { class: "acceso-marca" },
        h("div", { class: "logo" }, "Salud Integral"),
        h("div", {},
          h("h1", {}, "Pacientes y citas, en un solo lugar."),
          h("p", {}, "Registro de pacientes, agenda de citas e historia clínica con acceso según el cargo de cada persona.")),
        h("p", { class: "prototipo" }, "Prototipo académico. Los datos se guardan en memoria y se pierden al reiniciar el servidor; todos los pacientes son ficticios.")),
      h("section", { class: "acceso-form" }, formulario))
  );
}
