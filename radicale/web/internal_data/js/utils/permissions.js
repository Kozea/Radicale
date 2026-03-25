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

/**
 * @param {string} permissions
 * @param {HTMLElement} node
 */
export function displayPermissions(permissions, node) {
  permissions = (permissions || "").toLowerCase();
  if (permissions === "rw") {
    const roElement = node.querySelector("[data-name=ro]");
    if (roElement && roElement.parentNode) {
      roElement.parentNode.removeChild(roElement);
    }
  } else if (permissions === "r") {
    const rwElement = node.querySelector("[data-name=rw]");
    if (rwElement && rwElement.parentNode) {
      rwElement.parentNode.removeChild(rwElement);
    }
  } else {
    console.warn("Unknown permissions", permissions);
  }
}
