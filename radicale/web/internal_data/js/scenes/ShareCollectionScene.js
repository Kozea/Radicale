/**
 * This file is part of Radicale Server - Calendar Server
 * Copyright © 2017-2024 Unrud <unrud@outlook.com>
 * Copyright © 2023-2024 Matthew Hana <matthew.hana@gmail.com>
 * Copyright © 2024-2025 Peter Bieringer <pb@bieringer.de>
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

import {
  delete_share_by_map,
  delete_share_by_token,
  reload_sharing_list,
} from "../api/sharing.js";
import { Collection, Permission } from "../models/collection.js";
import { extract_title } from "../utils/collection_utils.js";

import { update_title_and_description } from "../utils/collection_utils.js";
import { ErrorHandler } from "../utils/error.js";
import { get_element, get_element_by_id } from "../utils/misc.js";
import { displayPermissionsOrConversion } from "../utils/permissions.js";
import { UrlTextHandler } from "../utils/url_text.js";
import { CreateEditShareScene } from "./CreateEditShareScene.js";
import { DeleteConfirmationScene } from "./DeleteConfirmationScene.js";
import { Scene, pop_scene, push_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class ShareCollectionScene {
  /**
   * @param {string} user
   * @param {?string} password
   * @param {Collection} collection The collection on which to edit sharing setting. Must exist.
   */
  constructor(user, password, collection) {
    this._user = user;
    this._password = password;
    this._collection = collection;

    this._html_scene = get_element_by_id("sharecollectionscene");
    this._cancel_btn = get_element(this._html_scene, "[data-name=cancel]");
    this._share_by_token_btn = get_element(this._html_scene, "button[data-name=sharebytoken]");
    this._share_by_map_btn = get_element(this._html_scene, "button[data-name=sharebymap]");
    this._share_by_token_div = get_element(this._html_scene, "div[data-name=sharebytoken]");
    this._share_by_map_div = get_element(this._html_scene, "div[data-name=sharebymap]");
    this._error_form = get_element(this._html_scene, "[data-name=error]");

    this._errorHandler = new ErrorHandler(this._error_form);

    this._title = get_element(this._html_scene, "[data-name=title]");
    this._description = get_element(this._html_scene, "[data-name=description]");
  }

  _oncancel() {
    try {
      pop_scene();
    } catch (err) {
      console.error(err);
    }
    return false;
  }

  _onsharebytoken() {
    let create_edit_share_scene = new CreateEditShareScene(this._user, this._password, this._collection, "token");
    push_scene(create_edit_share_scene);
  }

  _onsharebymap() {
    let create_edit_share_scene = new CreateEditShareScene(this._user, this._password, this._collection, "map");
    push_scene(create_edit_share_scene);
  }

  show() {
    this.release();
    this._html_scene.classList.remove("hidden");
    this._html_scene.querySelectorAll("details").forEach(function (details) {
      details.open = true;
    });
    this._cancel_btn.onclick = () => this._oncancel();

    let can_share_by_token = this._collection.has_permission(Permission.SHARE_TOKEN);
    let can_share_by_map = this._collection.has_permission(Permission.SHARE_MAP);

    if (can_share_by_token) {
      if (this._share_by_token_btn) {
        this._share_by_token_btn.classList.remove("hidden");
        this._share_by_token_btn.onclick = () => this._onsharebytoken();
      }
      if (this._share_by_token_div) this._share_by_token_div.classList.remove("hidden");
    } else {
      if (this._share_by_token_btn) this._share_by_token_btn.classList.add("hidden");
      if (this._share_by_token_div) this._share_by_token_div.classList.add("hidden");
    }

    if (can_share_by_map) {
      if (this._share_by_map_btn) {
        this._share_by_map_btn.classList.remove("hidden");
        this._share_by_map_btn.onclick = () => this._onsharebymap();
      }
      if (this._share_by_map_div) this._share_by_map_div.classList.remove("hidden");
    } else {
      if (this._share_by_map_btn) this._share_by_map_btn.classList.add("hidden");
      if (this._share_by_map_div) this._share_by_map_div.classList.add("hidden");
    }

    update_title_and_description(this._collection, this._title, this._description);
    update_share_list(this._user, this._password, this._collection, this._errorHandler);
  }

  hide() {
    this._html_scene.classList.add("hidden");
    this._cancel_btn.onclick = null;
  }

  release() {
  }

  is_transient() { return false; }

  title_object() {
    return extract_title(this._collection);
  }

}

/**
 * @param {string} user
 * @param {?string} password
 * @param {Collection} collection
 * @param {ErrorHandler} errorHandler
 */
function update_share_list(user, password, collection, errorHandler) {
  let share_rows = document.querySelectorAll(
    "[data-name=sharetokenrowtemplate], [data-name=sharemaprowtemplate]",
  );
  share_rows.forEach(function (row) {
    if (!row.classList.contains("hidden")) {
      if (row.parentNode) {
        row.parentNode.removeChild(row);
      }
    }
  });

  reload_sharing_list(user, password, collection, function (shares, error) {
    if (error) {
      errorHandler.setError(error);
    } else {
      add_share_rows(user, password, collection, shares, errorHandler);
    }
  });
}

/**
 * 
 * @param {string} user 
 * @param {?string} password 
 * @param {Collection} collection 
 * @param {import('../api/sharing.js').Share} share 
 * @param {HTMLElement} template 
 * @param {string} delete_label 
 * @param {function(string, string, import('../api/sharing.js').Share, function(?string):void):void} delete_action 
 * @param {ErrorHandler} errorHandler
 * @param {function():void} [onDeleteSuccess] Optional extra callback after a successful delete.
 */
function add_share_row_node(user, password, collection, share, template, delete_label, delete_action, errorHandler, onDeleteSuccess) {
  let pathortoken = share["PathOrToken"] || "";
  let node = /** @type {HTMLElement} */ (template.cloneNode(true));
  node.classList.remove("hidden");

  /** @type {HTMLInputElement} */ let pathortoken_form = /** @type {HTMLInputElement} */ (get_element(node, "[data-name=pathortoken]"));
  /** @type {HTMLButtonElement} */ let copy_btn = /** @type {HTMLButtonElement} */ (get_element(node, "[data-name=copy-url]"));
  if (pathortoken_form) {
    new UrlTextHandler(pathortoken_form, copy_btn).setHref(pathortoken);
  }

  let permissions = (share["Permissions"] || "").toLowerCase();
  displayPermissionsOrConversion(share["Conversion"], permissions, node);

  /** @type {HTMLElement} */ let edit_btn = get_element(node, "[data-name=edit]");
  edit_btn.onclick = function () {
    let create_edit_share_scene = new CreateEditShareScene(user, password, collection, share.ShareType, share);
    push_scene(create_edit_share_scene);
  };

  /** @type {HTMLElement} */ let delete_btn = get_element(node, "[data-name=delete]");
  delete_btn.onclick = function () {
    let delete_collection_scene = new DeleteConfirmationScene(
      user, password, "Delete Share", share, delete_label + " " + pathortoken, delete_action, false,
      function () {
        if (onDeleteSuccess) onDeleteSuccess();
        pop_scene();
        update_share_list(user, password, collection, errorHandler);
      }
    );
    push_scene(delete_collection_scene);
  };

  if (template.parentNode) {
    template.parentNode.insertBefore(node, template);
  }
}

/**
 * @param {string} user 
 * @param {?string} password 
 * @param {Collection} collection 
 * @param {Array<import('../api/sharing.js').Share>} shares 
 * @param {ErrorHandler} errorHandler
 */
function add_share_rows(user, password, collection, shares, errorHandler) {
  /** @type {HTMLElement} */ let token_template = get_element(document, "[data-name=sharetokenrowtemplate]");
  /** @type {HTMLElement} */ let map_template = get_element(document, "[data-name=sharemaprowtemplate]");
  shares.forEach(function (share) {
    let pathortoken = share["PathOrToken"] || "";
    let pathmapped = share["PathMapped"] || "";
    let decodedHref = decodeURIComponent(collection.href).replace(/\/+$/, "") + "/";
    let decodedPathMapped = decodeURIComponent(pathmapped).replace(/\/+$/, "") + "/";
    let decodedPathOrToken = decodeURIComponent(pathortoken).replace(/\/+$/, "") + "/";

    if (
      decodedHref.includes(decodedPathMapped) ||
      decodedHref.includes(decodedPathOrToken)
    ) {
      if (share["ShareType"] === "token") {
        add_share_row_node(user, password, collection, share, token_template, "share", delete_share_by_token, errorHandler);
      }
      else if (share["ShareType"] === "map") {
        add_share_row_node(user, password, collection, share, map_template, "map", delete_share_by_map, errorHandler);
      }
    }
  });
}

/**
 * @param {import('../api/sharing.js').ServerFeatures} features
 */
export function maybe_enable_sharing_options(features) {
  if (!features || !features.sharing) return;
  let has_sharing = features.sharing.ApiVersion !== undefined;

  let incomingshares_btn = document.querySelector("#collectionsscene [data-name=incomingshares]");
  if (incomingshares_btn) {
    if (has_sharing) {
      incomingshares_btn.classList.remove("hidden");
    } else {
      incomingshares_btn.classList.add("hidden");
    }
  }
}
