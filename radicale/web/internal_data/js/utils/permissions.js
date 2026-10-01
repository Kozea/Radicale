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

import { CollectionType, Permission } from "../models/collection.js";
import { get_element } from "../utils/misc.js";

/**
 * @param {string | import("../models/collection.js").Collection | boolean} permissions
 * @param {HTMLElement} node
 */
export function displayPermissions(permissions, node) {
  const roElement = get_element(node, "[data-name=ro]");
  const rwElement = get_element(node, "[data-name=rw]");
  let is_write = false;
  if (typeof permissions === "boolean") {
    is_write = permissions;
  } else if (typeof permissions === "string") {
    is_write = permissions.toLowerCase().includes('w');
  } else if (permissions && typeof permissions.has_permission === "function") {
    if (permissions.type === CollectionType.WEBCAL) {
      is_write = false;
    } else {
      is_write = permissions.has_permission(Permission.WRITE) ||
        permissions.has_permission(Permission.WRITE_CONTENT);
    }
  }
  if (is_write) {
    rwElement.classList.remove("hidden");
    rwElement.setAttribute("title", "Read and write");
    roElement.classList.add("hidden");
  } else {
    roElement.classList.remove("hidden");
    roElement.setAttribute("title", "Read-only");
    rwElement.classList.add("hidden");
  }
}

/**
 * @param {string} conversion
 * @param {string} permissions
 * @param {HTMLElement} node
 */
export function displayPermissionsOrConversion(conversion, permissions, node) {
  const conversionElement = node.querySelector("[data-name=conversion]");
  let fixedConversion = (conversion || "").toLowerCase();
  if (conversionElement && fixedConversion !== "none" && fixedConversion !== "") {
    conversionElement.classList.remove("hidden");
    conversionElement.setAttribute("title", "Converted");
    const roElement = node.querySelector("[data-name=ro]");
    const rwElement = node.querySelector("[data-name=rw]");
    if (roElement) roElement.classList.add("hidden");
    if (rwElement) rwElement.classList.add("hidden");
  } else {
    if (conversionElement) {
      conversionElement.classList.add("hidden");
    }
    displayPermissions(permissions, node);
  }
}
