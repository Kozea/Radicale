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
  delete_share_by_bday,
  delete_share_by_map,
  delete_share_by_token,
  reload_sharing_list,
} from "../api/sharing.js";
import { Collection, CollectionType } from "../models/collection.js";
import { collectionsCache } from "../utils/collections_cache.js";
import { ErrorHandler } from "../utils/error.js";
import { displayPermissions } from "../utils/permissions.js";
import { CreateEditShareScene } from "./CreateEditShareScene.js";
import { DeleteConfirmationScene } from "./DeleteConfirmationScene.js";
import { Scene, pop_scene, push_scene } from "./scene_manager.js";

/**
 * @implements {Scene}
 */
export class ShareCollectionScene {
  /**
   * @param {string} user
   * @param {string} password
   * @param {Collection} collection The collection on which to edit sharing setting. Must exist.
   */
  constructor(user, password, collection) {

    let html_scene = document.getElementById("sharecollectionscene");

    /** @type {HTMLElement} */ let cancel_btn = html_scene.querySelector("[data-name=cancel]");
    /** @type {HTMLElement} */ let share_by_token_btn = html_scene.querySelector(
      "button[data-name=sharebytoken]"
    );
     /** @type {HTMLElement} */ let share_by_map_btn = html_scene.querySelector(
      "button[data-name=sharebymap]"
    );
     /** @type {HTMLElement} */ let share_by_bday_btn = html_scene.querySelector(
      "button[data-name=sharebybday]"
    );
    /** @type {HTMLElement} */ let share_by_token_div = html_scene.querySelector(
      "div[data-name=sharebytoken]"
    );
    /** @type {HTMLElement} */ let share_by_map_div = html_scene.querySelector(
      "div[data-name=sharebymap]"
    );
    /** @type {HTMLElement} */ let share_by_bday_div = html_scene.querySelector(
      "div[data-name=sharebybday]"
    );
    /** @type {HTMLElement} */ let error_form = html_scene.querySelector("[data-name=error]");

    let errorHandler = new ErrorHandler(error_form);

    /** @type {HTMLElement} */ let title = html_scene.querySelector("[data-name=title]");

    function oncancel() {
      try {
        pop_scene();
      } catch (err) {
        console.error(err);
      }
      return false;
    }

    function onsharebytoken() {
      let create_edit_share_scene = new CreateEditShareScene(user, password, collection, "token");
      push_scene(create_edit_share_scene);
    }

    function onsharebymap() {
      let create_edit_share_scene = new CreateEditShareScene(user, password, collection, "map");
      push_scene(create_edit_share_scene);
    }

    function onsharebybday() {
      let create_edit_share_scene = new CreateEditShareScene(user, password, collection, "bday");
      push_scene(create_edit_share_scene);
    }

    this.show = function () {
      this.release();
      html_scene.classList.remove("hidden");
      html_scene.querySelectorAll("details").forEach(function (details) {
        details.open = true;
      });
      cancel_btn.onclick = oncancel;

      collectionsCache.getServerFeatures(user, password, errorHandler.setError, (features) => {
        if (features.sharing && features.sharing.PermittedCreateCollectionByToken) {
          if (share_by_token_btn) {
            share_by_token_btn.classList.remove("hidden");
            share_by_token_btn.onclick = onsharebytoken;
          }
        } else {
          if (share_by_token_btn) share_by_token_btn.classList.add("hidden");
        }

        if (features.sharing && features.sharing.FeatureEnabledCollectionByToken) {
          if (share_by_token_div) share_by_token_div.classList.remove("hidden");
        } else {
          if (share_by_token_div) share_by_token_div.classList.add("hidden");
        }

        if (features.sharing && features.sharing.PermittedCreateCollectionByMap) {
          if (share_by_map_btn) {
            share_by_map_btn.classList.remove("hidden");
            share_by_map_btn.onclick = onsharebymap;
          }
        } else {
          if (share_by_map_btn) share_by_map_btn.classList.add("hidden");
        }

        if (features.sharing && features.sharing.FeatureEnabledCollectionByMap) {
          if (share_by_map_div) share_by_map_div.classList.remove("hidden");
        } else {
          if (share_by_map_div) share_by_map_div.classList.add("hidden");
        }

        if (features.sharing && features.sharing.PermittedCreateCollectionByBday) {
          let is_addressbook = collection.type === CollectionType.ADDRESSBOOK;
          if (share_by_bday_btn) {
            if (is_addressbook) {
              share_by_bday_btn.classList.remove("hidden");
              share_by_bday_btn.onclick = onsharebybday;
            } else {
              share_by_bday_btn.classList.add("hidden");
            }
          }
        } else {
          if (share_by_bday_btn) share_by_bday_btn.classList.add("hidden");
        }

        if (features.sharing && features.sharing.FeatureEnabledCollectionByBday && collection.type === CollectionType.ADDRESSBOOK) {
          if (share_by_bday_div) share_by_bday_div.classList.remove("hidden");
        } else {
          if (share_by_bday_div) share_by_bday_div.classList.add("hidden");
        }
      });

      title.textContent = collection.displayname || collection.href;
      update_share_list(user, password, collection, errorHandler);
    };
    this.hide = function () {
      html_scene.classList.add("hidden");
      cancel_btn.onclick = null;
    };
    this.release = function () {
    };
  }
}

/**
 * @param {string} user
 * @param {string} password
 * @param {Collection} collection
 * @param {ErrorHandler} errorHandler
 */
function update_share_list(user, password, collection, errorHandler) {
  let share_rows = document.querySelectorAll(
    "[data-name=sharetokenrowtemplate], [data-name=sharemaprowtemplate], [data-name=sharebdayrowtemplate]",
  );
  share_rows.forEach(function (row) {
    if (!row.classList.contains("hidden")) {
      row.parentNode.removeChild(row);
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
 * @param {string} password 
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

  /** @type {HTMLInputElement} */ let pathortoken_form = node.querySelector("[data-name=pathortoken]");
  if (pathortoken_form) {
    pathortoken_form.value = pathortoken;
  }

  let permissions = (share["Permissions"] || "").toLowerCase();
  displayPermissions(permissions, node);

  /** @type {HTMLElement} */ let edit_btn = node.querySelector("[data-name=edit]");
  edit_btn.onclick = function () {
    let create_edit_share_scene = new CreateEditShareScene(user, password, collection, share.ShareType, share);
    push_scene(create_edit_share_scene);
  };

  /** @type {HTMLElement} */ let delete_btn = node.querySelector("[data-name=delete]");
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

  template.parentNode.insertBefore(node, template);
}

/**
 * @param {string} user 
 * @param {string} password 
 * @param {Collection} collection 
 * @param {Array<import('../api/sharing.js').Share>} shares 
 * @param {ErrorHandler} errorHandler
 */
function add_share_rows(user, password, collection, shares, errorHandler) {
  /** @type {HTMLElement} */ let token_template = document.querySelector("[data-name=sharetokenrowtemplate]");
  /** @type {HTMLElement} */ let map_template = document.querySelector("[data-name=sharemaprowtemplate]");
  /** @type {HTMLElement} */ let bday_template = document.querySelector("[data-name=sharebdayrowtemplate]");
  shares.forEach(function (share) {
    let pathortoken = share["PathOrToken"] || "";
    let pathmapped = share["PathMapped"] || "";
    if (
      collection.href.includes(pathmapped) ||
      collection.href.includes(pathortoken)
    ) {
      if (share["ShareType"] === "token") {
        add_share_row_node(user, password, collection, share, token_template, "share", delete_share_by_token, errorHandler);
      } else if (share["ShareType"] === "map") {
        add_share_row_node(user, password, collection, share, map_template, "map", delete_share_by_map, errorHandler);
      } else if (share["ShareType"] === "bday") {
        let onDeleteSuccess = (share["User"] === user) ? function () { collectionsCache.invalidate(); } : undefined;
        add_share_row_node(user, password, collection, share, bday_template, "bday", delete_share_by_bday, errorHandler, onDeleteSuccess);
      }
    }
  });
}

/**
 * @param {import('../api/sharing.js').ServerFeatures} features
 */
export function maybe_enable_sharing_options(features) {
  if (!features || !features.sharing) return;
  let map_is_enabled = features.sharing.FeatureEnabledCollectionByMap || false;
  let token_is_enabled = features.sharing.FeatureEnabledCollectionByToken || false;
  let bday_is_enabled = features.sharing.FeatureEnabledCollectionByBday || false;
  if (map_is_enabled || token_is_enabled || bday_is_enabled) {
    let share_options = document.querySelectorAll("[data-name=shareoption]");
    for (let i = 0; i < share_options.length; i++) {
      let share_option = share_options[i];
      share_option.classList.remove("hidden");
    }
  }
}
