/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2026-2026 Max Berger <max@berger.name>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import { get_element } from "../utils/misc.js";

/**
 * @param {string} conversion
 * @param {string} permissions
 * @param {HTMLElement} node
 */
export function displayPermissionsOrConversion(conversion, permissions, node) {
  const conversionElement = get_element(node, "[data-name=conversion]");
  const roElement = get_element(node, "[data-name=ro]");
  const rwElement = get_element(node, "[data-name=rw]");
  let fixedConversion = (conversion || "").toLowerCase();
  if (fixedConversion != "none" && fixedConversion != "") {
    conversionElement.classList.remove("hidden");
    conversionElement.setAttribute("title", "Converted");
    roElement.classList.add("hidden");
    rwElement.classList.add("hidden");
  } else {
    permissions = (permissions || "").toLowerCase();
    if (permissions === "rw") {
      rwElement.classList.remove("hidden");
      rwElement.setAttribute("title", "Read and write");
      roElement.classList.add("hidden");
      conversionElement.classList.add("hidden");
    } else if (permissions === "r") {
      roElement.classList.remove("hidden");
      roElement.setAttribute("title", "Read-only");
      rwElement.classList.add("hidden");
      conversionElement.classList.add("hidden");
    } else {
      console.warn("Unknown permissions", permissions);
    }
  }
}
