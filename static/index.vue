<template id="page-watchonly">
  <div class="row q-col-gutter-md">
    <div class="col-12 col-md-7 q-gutter-y-md">
      <wallet-config
        :total="utxos.total"
        v-model:config-data="config"
        :adminkey="g.user.wallets[0].adminkey"
      >
        <template v-slot:trezor>
          <trezor-signer
            ref="trezorSigner"
            :network="config.network"
            @signed:tx="updateSignedTx"
            @device:connected="handleDeviceConnected"
          ></trezor-signer>
        </template>
        <template v-slot:serial>
          <serial-signer
            ref="serialSigner"
            :network="config.network"
            :sats-denominated="config.sats_denominated"
            @signed:psbt="updateSignedPsbt"
            @device:connected="handleDeviceConnected"
            class="q-pr-lg float-right"
          ></serial-signer>
        </template>
      </wallet-config>

      <wallet-list
        v-if="config.isLoaded"
        :adminkey="g.user.wallets[0].adminkey"
        :inkey="g.user.wallets[0].inkey"
        :sats-denominated="config.sats_denominated"
        :network="config.network"
        :addresses="addresses"
        :serial-signer-ref="signerDevice"
        @accounts-update="updateAccounts"
        @new-receive-address="showAddressDetailsWithConfirmation"
      >
      </wallet-list>

      <q-card>
        <div class="row q-pt-sm q-pb-sm items-center no-wrap q-mb-md">
          <div class="col-md-3 col-sm-5 q-pl-md">
            <q-btn
              unelevated
              class="btn-full"
              outline
              @click="scanAllAddresses"
              :disabled="scan.scanning == true || showPayment"
              v-text="$t('watchonly.scan_blockchain')"
            ></q-btn>
          </div>
          <div class="col-md-6 col-sm-2 q-pl-md">
            <q-spinner
              v-if="scan.scanning == true"
              color="primary"
              size="2.55em"
            ></q-spinner>
          </div>
          <div class="col-md-3 col-sm-5 q-pr-md">
            <q-btn-dropdown
              v-if="!showPayment"
              split
              unelevated
              outline
              :label="$t('watchonly.new_payment')"
              class="btn-full"
              @click="goToPaymentView"
            >
              <q-list>
                <q-item @click="goToPaymentView" clickable v-close-popup>
                  <q-item-section>
                    <q-item-label
                      v-text="$t('watchonly.new_payment')"
                    ></q-item-label>
                    <q-item-label
                      caption
                      v-text="$t('watchonly.new_payment_desc')"
                    ></q-item-label>
                  </q-item-section>
                </q-item>
                <q-item
                  @click="showEnterSignedPsbtDialog"
                  clickable
                  v-close-popup
                >
                  <q-item-section>
                    <q-item-label
                      v-text="$t('watchonly.from_signed_psbt')"
                    ></q-item-label>
                    <q-item-label
                      caption
                      v-text="$t('watchonly.from_signed_psbt_desc')"
                    ></q-item-label>
                  </q-item-section>
                </q-item>
              </q-list>
            </q-btn-dropdown>

            <q-btn
              v-if="showPayment"
              outline
              color="gray"
              class="btn-full"
              @click="showPayment = false"
              v-text="$t('watchonly.back')"
            ></q-btn>
          </div>
        </div>

        <div v-if="scan.scanning == true">
          <q-linear-progress
            :value="scan.scanIndex / scan.scanCount"
            size="10px"
            color="primary"
            class="q-mt-sm"
          ></q-linear-progress>
        </div>
      </q-card>

      <q-card v-if="config.isLoaded">
        <q-card-section v-show="!showPayment">
          <q-tabs v-model="tab" no-caps class="bg-dark text-white shadow-2">
            <q-tab name="addresses" :label="$t('watchonly.addresses')"></q-tab>
            <q-tab name="history" :label="$t('watchonly.history')"></q-tab>
            <q-tab name="utxos" :label="$t('watchonly.utxos')"></q-tab>
          </q-tabs>
          <q-tab-panels v-model="tab">
            <q-tab-panel name="addresses">
              <address-list
                ref="addressList"
                :addresses="addresses"
                :accounts="walletAccounts"
                :mempool-endpoint="mempoolHostname"
                :sats-denominated="config.sats_denominated"
                @scan:address="scanAddress"
                @show-address-details="showAddressDetails"
                @update:addresses="initUtxos"
                @search:tab="searchInTab"
                @update:note="updateNoteForAddress"
                :inkey="g.user.wallets[0].inkey"
              >
              </address-list>
            </q-tab-panel>
            <q-tab-panel name="history">
              <history
                :history="history"
                :mempool-endpoint="mempoolHostname"
                :sats-denominated="config.sats_denominated"
                :filter="historyFilter"
              ></history>
            </q-tab-panel>
            <q-tab-panel name="utxos">
              <utxo-list
                :utxos="utxos.data"
                :mempool-endpoint="mempoolHostname"
                :accounts="walletAccounts"
                :sats-denominated="config.sats_denominated"
                :filter="utxosFilter"
              ></utxo-list>
            </q-tab-panel>
          </q-tab-panels>
        </q-card-section>
      </q-card>
      <div v-if="config.isLoaded" class="q-pt-sm">
        <payment
          ref="paymentRef"
          v-show="showPayment"
          :accounts="walletAccounts"
          :addresses="addresses"
          :utxos="utxos.data"
          :mempool-endpoint="mempoolHostname"
          :adminkey="g.user.wallets[0].adminkey"
          :serial-signer-ref="signerDevice"
          :sats-denominated="config.sats_denominated"
          :network="config.network"
          @broadcast-done="handleBroadcastSuccess"
        ></payment>
        <!-- todo: no more utxos.data -->
      </div>
    </div>

    <div class="col-12 col-md-5 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <h6
            class="text-subtitle1 q-my-none"
            v-text="$t('watchonly.extension_title')"
          ></h6>
        </q-card-section>
        <q-card-section class="q-pa-none">
          <q-separator></q-separator>
          <q-list>
            <q-card>
              <q-card-section>
                <p>
                  <span v-text="$t('watchonly.extension_desc')"></span><br />
                  <span v-text="$t('watchonly.extension_desc2')"></span>
                  <a
                    class="text-secondary"
                    href="https://iancoleman.io/bip39/"
                    target="_blank"
                    style="color: unset"
                    >https://iancoleman.io/bip39/</a
                  >
                  <br />
                  <span v-text="$t('watchonly.flash_binaries')"></span>
                  <a
                    class="text-secondary"
                    href="https://lnbits.github.io/hardware-wallet"
                    target="_blank"
                    style="color: unset"
                    v-text="$t('watchonly.directly_from_browser')"
                  ></a>
                  <small>
                    <br /><span v-text="$t('watchonly.created_by')"></span>
                    <a
                      class="text-secondary"
                      target="_blank"
                      style="color: unset"
                      href="https://github.com/arcbtc"
                      >Ben Arc</a
                    >,
                    <a
                      class="text-secondary"
                      target="_blank"
                      style="color: unset"
                      href="https://github.com/talvasconcelos"
                      >Tiago Vasconcelos</a
                    >,
                    <a
                      class="text-secondary"
                      target="_blank"
                      style="color: unset"
                      href="https://github.com/motorina0"
                      >motorina0</a
                    >
                    (using,
                    <a
                      class="text-secondary"
                      target="_blank"
                      style="color: unset"
                      href="https://github.com/diybitcoinhardware/embit"
                      >Embit</a
                    ></small
                  >)
                  <br />
                  <br />
                  <a
                    class="text-secondary"
                    target="_blank"
                    href="/docs#/watchonly"
                    style="color: unset"
                    v-text="$t('watchonly.swagger_docs')"
                  ></a>
                </p>
              </q-card-section>
            </q-card>
          </q-list>
        </q-card-section>
      </q-card>
    </div>
    <q-dialog v-model="showAddress" position="top">
      <q-card class="q-pa-lg lnbits__dialog-card">
        <h5
          class="text-subtitle1 q-my-none"
          v-text="$t('watchonly.address_details')"
        ></h5>
        <q-separator></q-separator><br />

        <q-responsive :ratio="1" class="q-mx-xl q-mb-md">
          <lnbits-qrcode
            v-if="currentAddress"
            :value="currentAddress.address"
          ></lnbits-qrcode>
        </q-responsive>
        <p v-if="currentAddress">
          <q-btn
            flat
            dense
            size="ms"
            icon="content_copy"
            @click="copyText(currentAddress.address)"
            class="q-ml-sm"
          ></q-btn>
          <span v-text="currentAddress.address"></span>
          <q-btn
            flat
            dense
            size="ms"
            icon="launch"
            type="a"
            :href="
              'https://' +
              mempoolHostname +
              '/address/' +
              currentAddress.address
            "
            target="_blank"
          ></q-btn>
        </p>
        <p v-if="currentAddress">
          <q-input
            filled
            dense
            v-model.trim="addressNote"
            type="text"
            :label="$t('watchonly.note')"
          ></q-input>
        </p>
        <div v-if="currentAddress && currentAddress.gapLimitExceeded">
          <q-badge
            color="yellow"
            text-color="black"
            v-text="$t('watchonly.gap_limit_exceeded')"
          ></q-badge>
        </div>
        <div class="row q-mt-lg q-gutter-sm">
          <q-btn
            v-if="currentAddress"
            outline
            v-close-popup
            color="grey"
            @click="
              updateNoteForAddress({
                addressId: currentAddress.id,
                note: addressNote
              })
            "
            class="q-ml-sm"
            v-text="$t('watchonly.save_note')"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('watchonly.close')"
          ></q-btn>
        </div>
        <div class="row q-mt-lg q-gutter-sm"></div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showEnterSignedPsbt" position="top">
      <q-card class="q-pa-lg lnbits__dialog-card">
        <h5
          class="text-subtitle1 q-my-none"
          v-text="$t('watchonly.enter_signed_psbt')"
        ></h5>
        <q-separator></q-separator><br />

        <p>
          <q-input
            filled
            dense
            v-model.trim="signedBase64Psbt"
            type="textarea"
            :label="$t('watchonly.signed_psbt')"
          ></q-input>
        </p>

        <div class="row q-mt-lg q-gutter-sm">
          <q-btn
            outline
            v-close-popup
            color="grey"
            @click="checkPsbt"
            class="q-ml-sm"
            v-text="$t('watchonly.check_psbt')"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('watchonly.close')"
          ></q-btn>
        </div>
        <div class="row q-mt-lg q-gutter-sm"></div>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="wallet-config">
  <div>
    <q-card>
      <div class="row items-center no-wrap q-mb-md q-pt-sm q-pb-sm">
        <div class="col-lg-2 col-sm-3 q-ml-lg">
          <q-btn
            unelevated
            @click="show = true"
            color="primary"
            icon="settings"
          >
          </q-btn>
        </div>
        <div class="col-lg-5 col-sm-3">
          <div class="row justify-center q-gutter-x-md items-center">
            <div :class="{'text-h4': $q.screen.gt.md}">{{ satBtc(total) }}</div>
          </div>
        </div>
        <div class="col-lg-3 col-sm-3 q-pr-lg">
          <div class="float-right">
            <slot name="trezor"></slot>
          </div>
        </div>
        <div class="col-lg-2 col-sm-3 q-pr-lg">
          <slot name="serial"></slot>
        </div>
      </div>
    </q-card>

    <q-dialog v-model="show" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="updateConfig" class="q-gutter-md">
          <q-input
            filled
            dense
            v-model.trim="config.mempool_endpoint"
            type="text"
            :label="$t('watchonly.mempool_endpoint')"
          >
          </q-input>

          <q-input
            filled
            dense
            v-model.number="config.receive_gap_limit"
            type="number"
            min="0"
            :label="$t('watchonly.receive_gap_limit')"
          ></q-input>

          <q-input
            filled
            dense
            v-model.number="config.change_gap_limit"
            type="number"
            min="0"
            :label="$t('watchonly.change_gap_limit')"
          ></q-input>

          <q-select
            filled
            dense
            emit-value
            v-model="config.network"
            :options="networkOptions"
            :label="$t('watchonly.network')"
          ></q-select>

          <q-toggle
            :label="
              config.sats_denominated
                ? $t('watchonly.sats_denominated')
                : $t('watchonly.btc_denominated')
            "
            color="primary"
            v-model="config.sats_denominated"
          ></q-toggle>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="!config.mempool_endpoint"
              type="submit"
              v-text="$t('watchonly.update')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              v-text="$t('watchonly.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="utxo-list">
  <q-card>
    <q-card-section>
      <div class="row items-center no-wrap q-mb-md">
        <div v-if="selectable" class="col-3 q-pr-lg">
          <q-select
            filled
            dense
            emit-value
            v-model="utxoSelectionMode"
            :options="utxoSelectionModes"
            :label="$t('watchonly.selection_mode')"
            @input="updateUtxoSelection"
          ></q-select>
        </div>
        <div v-if="selectable" class="col-1 q-pr-lg">
          <q-btn
            outline
            icon="refresh"
            color="grey"
            @click="updateUtxoSelection"
            class="q-ml-sm"
          ></q-btn>
        </div>
        <div v-if="selectable" class="col-5 q-pr-lg"></div>
        <div v-if="!selectable" class="col-9 q-pr-lg"></div>
        <div class="col-3 float-right">
          <q-input
            borderless
            dense
            debounce="300"
            v-model="filter"
            :placeholder="$t('watchonly.search')"
          >
            <template v-slot:append>
              <q-icon name="search"></q-icon>
            </template>
          </q-input>
        </div>
      </div>

      <q-table
        flat
        dense
        :rows="utxos"
        row-key="id"
        :columns="columns"
        :pagination.sync="utxosTable.pagination"
        :filter="filter"
      >
        <template v-slot:body="props">
          <q-tr :props="props">
            <q-td auto-width>
              <q-btn
                size="sm"
                color="primary"
                round
                dense
                @click="props.row.expanded = !props.row.expanded"
                :icon="props.row.expanded ? 'remove' : 'add'"
              />
            </q-td>

            <q-td v-if="selectable" key="selected" :props="props">
              <div>
                <q-checkbox v-model="props.row.selected"></q-checkbox>
              </div>
            </q-td>
            <q-td key="status" :props="props">
              <div>
                <q-badge
                  v-if="props.row.confirmed"
                  @click="props.row.expanded = !props.row.expanded"
                  color="primary"
                  class="q-mr-md cursor-pointer"
                  v-text="$t('watchonly.confirmed')"
                >
                </q-badge>
                <q-badge
                  v-if="!props.row.confirmed"
                  @click="props.row.expanded = !props.row.expanded"
                  color="secondary"
                  class="q-mr-md cursor-pointer"
                  v-text="$t('watchonly.pending')"
                >
                </q-badge>
              </div>
            </q-td>
            <q-td key="address" :props="props">
              <div>
                <a
                  style="color: unset"
                  :href="
                    'https://' +
                    mempoolEndpoint +
                    '/address/' +
                    props.row.address
                  "
                  target="_blank"
                  v-text="props.row.address"
                ></a>
                <q-badge
                  v-if="props.row.isChange"
                  color="primary"
                  class="q-mr-md"
                  v-text="$t('watchonly.change')"
                >
                </q-badge>
                <q-badge
                  v-if="props.row.accountType === 'p2tr'"
                  color="yellow"
                  text-color="black"
                  v-text="$t('watchonly.taproot')"
                >
                </q-badge>
              </div>
            </q-td>

            <q-td
              key="amount"
              :props="props"
              class="text-green-13 text-weight-bold"
            >
              <div v-text="satBtc(props.row.amount)"></div>
            </q-td>
            <q-td key="date" :props="props" v-text="props.row.date"></q-td>
            <q-td key="wallet" :props="props">
              <div v-text="getWalletName(props.row.wallet)"></div>
            </q-td>
          </q-tr>
          <q-tr v-show="props.row.expanded" :props="props">
            <q-td colspan="100%">
              <div class="row items-center q-mb-md">
                <div
                  class="col-2 q-pr-lg"
                  v-text="$t('watchonly.transaction_id')"
                ></div>
                <div class="col-10 q-pr-lg">
                  <a
                    style="color: unset"
                    :href="
                      'https://' + mempoolEndpoint + '/tx/' + props.row.txId
                    "
                    target="_blank"
                    v-text="props.row.txId"
                  ></a>
                </div>
              </div>
            </q-td>
          </q-tr>
        </template>
      </q-table> </q-card-section
  ></q-card>
</template>

<template id="wallet-list">
  <q-card>
    <q-card-section>
      <div class="row items-center no-wrap q-mb-md">
        <div class="col-4">
          <q-btn-dropdown
            split
            unelevated
            :label="$t('watchonly.add_wallet_account')"
            color="primary"
            @click="showAddAccountDialog"
          >
            <q-list>
              <q-item @click="showAddAccountDialog" clickable v-close-popup>
                <q-item-section>
                  <q-item-label
                    v-text="$t('watchonly.new_account')"
                  ></q-item-label>
                  <q-item-label
                    caption
                    v-text="$t('watchonly.enter_account_xpub_or_descriptor')"
                  ></q-item-label>
                </q-item-section>
              </q-item>
              <q-item @click="getXpubFromDevice" clickable v-close-popup>
                <q-item-section>
                  <q-item-label
                    v-text="$t('watchonly.from_hardware_device')"
                  ></q-item-label>
                  <q-item-label
                    caption
                    v-text="$t('watchonly.get_xpub_from_device')"
                  >
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-btn-dropdown>
        </div>
        <div class="col-4 q-pl-lg"></div>
        <div class="col-4 q-pl-lg">
          <q-input
            borderless
            dense
            debounce="300"
            v-model="filter"
            :placeholder="$t('watchonly.search')"
          >
            <template v-slot:append>
              <q-icon name="search"></q-icon>
            </template>
          </q-input>
        </div>
      </div>
      <q-table
        flat
        dense
        :rows="walletAccounts"
        row-key="id"
        :columns="walletsTableColumns"
        v-model:pagination="walletsTable.pagination"
        :filter="filter"
      >
        <template v-slot:header="props">
          <q-tr :props="props">
            <q-th auto-width></q-th>
            <q-th
              v-for="col in props.cols"
              :key="col.name"
              :props="props"
              auto-width
            >
              <span v-text="col.label"></span>
            </q-th>
            <q-th auto-width></q-th>
          </q-tr>
        </template>
        <template v-slot:body="props">
          <q-tr :props="props">
            <q-td auto-width>
              <q-btn
                size="sm"
                color="primary"
                round
                dense
                @click="props.row.expanded = !props.row.expanded"
                :icon="props.row.expanded ? 'remove' : 'add'"
              />
            </q-td>
            <q-td key="new">
              <q-badge
                size="lg"
                color="primary"
                class="q-mr-md cursor-pointer"
                @click="openGetFreshAddressDialog(props.row.id)"
                v-text="$t('watchonly.new_receive_address')"
              >
              </q-badge>
            </q-td>

            <q-td key="title" :props="props">
              <div v-text="props.row.title"></div>
            </q-td>
            <q-td key="amount" :props="props">
              <div v-text="getAmmountForWallet(props.row.id)"></div>
            </q-td>
            <q-td key="type" :props="props">
              <div v-text="props.row.type"></div>
            </q-td>
            <q-td key="id" :props="props">
              <div v-text="props.row.id"></div>
            </q-td>
          </q-tr>
          <q-tr v-show="props.row.expanded" :props="props">
            <q-td colspan="100%">
              <div class="row items-center q-mt-md q-mb-lg">
                <div class="col-2 q-pr-lg"></div>
                <div class="col-4 q-pr-lg">
                  <q-btn
                    color="primary"
                    @click="openGetFreshAddressDialog(props.row.id)"
                    v-text="$t('watchonly.new_receive_address')"
                  ></q-btn>
                </div>

                <div class="col-4">
                  <span v-text="getAccountDescription(props.row.type)"></span>
                </div>
                <div class="col-2 q-pr-lg"></div>
              </div>

              <div class="row items-center no-wrap q-mb-md">
                <div
                  class="col-2 q-pr-lg"
                  v-text="$t('watchonly.master_pubkey')"
                ></div>
                <div class="col-7 q-pr-lg">
                  <q-input v-model="props.row.masterpub" filled readonly />
                </div>
                <div class="col-1">
                  <q-btn
                    unelevated
                    dense
                    size="md"
                    icon="qr_code"
                    :color="$q.dark.isActive ? 'grey-7' : 'grey-5'"
                    @click="openQrCodeDialog(props.row.masterpub)"
                  ></q-btn>
                </div>
                <div class="col-2 q-pr-lg">
                  <q-btn
                    outline
                    color="grey"
                    icon="content_copy"
                    @click="copyText(props.row.masterpub)"
                    class="q-ml-sm"
                  ></q-btn>
                </div>
              </div>
              <div
                v-if="props.row.meta?.xpub"
                class="row items-center no-wrap q-mb-md"
              >
                <div class="col-2 q-pr-lg" v-text="$t('watchonly.xpub')"></div>
                <div class="col-7 q-pr-lg">
                  <q-input v-model="props.row.meta.xpub" filled readonly />
                </div>
                <div class="col-1">
                  <q-btn
                    unelevated
                    dense
                    size="md"
                    icon="qr_code"
                    :color="$q.dark.isActive ? 'grey-7' : 'grey-5'"
                    @click="openQrCodeDialog(props.row.meta.xpub)"
                  ></q-btn>
                </div>
                <div class="col-2 q-pr-lg">
                  <q-btn
                    outline
                    color="grey"
                    icon="content_copy"
                    @click="copyText(props.row.meta.xpub)"
                    class="q-ml-sm"
                  ></q-btn>
                </div>
              </div>
              <div class="row items-center no-wrap q-mb-md">
                <div
                  class="col-2 q-pr-lg"
                  v-text="$t('watchonly.last_address_index')"
                ></div>
                <div class="col-8">
                  <span
                    v-if="props.row.address_no >= 0"
                    v-text="props.row.address_no"
                  >
                  </span>
                  <span
                    v-if="props.row.address_no < 0"
                    v-text="$t('watchonly.none')"
                  ></span>
                </div>
                <div class="col-2 q-pr-lg"></div>
              </div>
              <div class="row items-center no-wrap q-mb-md">
                <div
                  class="col-2 q-pr-lg"
                  v-text="$t('watchonly.fingerprint')"
                ></div>
                <div class="col-8" v-text="props.row.fingerprint"></div>
                <div class="col-2 q-pr-lg"></div>
              </div>
              <div class="row items-center q-mt-md q-mb-lg">
                <div class="col-2 q-pr-lg"></div>
                <div class="col-4 q-pr-lg">
                  <q-btn
                    unelevated
                    color="grey"
                    icon="cancel"
                    @click="deleteWalletAccount(props.row.id)"
                    v-text="$t('watchonly.delete')"
                  ></q-btn>
                </div>
                <div class="col-4"></div>
                <div class="col-2 q-pr-lg"></div>
              </div>
            </q-td>
          </q-tr>
        </template>
      </q-table>
    </q-card-section>
  </q-card>

  <q-dialog v-model="formDialog.show" position="top" @hide="closeFormDialog">
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <q-form @submit="addWalletAccount" class="q-gutter-md">
        <q-input
          filled
          dense
          v-model.trim="formDialog.data.title"
          type="text"
          :label="$t('watchonly.title')"
        ></q-input>
        <q-input
          v-if="!formDialog.useSerialPort"
          filled
          type="textarea"
          v-model="formDialog.data.masterpub"
          height="50px"
          autogrow
          :label="$t('watchonly.account_key_label')"
        ></q-input>
        <q-select
          v-if="formDialog.useSerialPort"
          filled
          dense
          emit-value
          v-model="formDialog.addressType"
          :options="addressTypeOptions"
          :label="$t('watchonly.address_type')"
          @input="handleAddressTypeChanged"
        ></q-select>

        <q-input
          v-if="formDialog.useSerialPort"
          filled
          type="text"
          v-model="accountPath"
          height="50px"
          autogrow
          :label="$t('watchonly.account_path')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            unelevated
            color="primary"
            :label="$t('watchonly.add_watch_only_account')"
            :disable="
              (formDialog.data.masterpub == null && accountPath == null) ||
              formDialog.data.title == null ||
              showCreating
            "
            type="submit"
          >
          </q-btn>
          <q-spinner v-if="showCreating" color="primary" size="2em"></q-spinner>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('watchonly.cancel')"
          ></q-btn>
        </div>
      </q-form>
    </q-card>
  </q-dialog>
  <q-dialog v-model="showQrCodeDialog" position="top">
    <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
      <q-responsive :ratio="1" class="q-mx-xl q-mb-md">
        <lnbits-qrcode :value="qrCodeValue"></lnbits-qrcode>
      </q-responsive>
    </q-card>
  </q-dialog>
</template>

<template id="address-list">
  <div>
    <div class="row items-center no-wrap q-mb-md">
      <div class="col q-pr-lg">
        <q-select
          filled
          clearable
          dense
          emit-value
          v-model="selectedWallet"
          :options="accounts"
          :label="$t('watchonly.wallet_account')"
        ></q-select>
      </div>
      <div class="col q-pr-lg">
        <q-select
          filled
          clearable
          dense
          emit-value
          multiple
          :options="filterOptions"
          v-model="filterValues"
          :label="$t('watchonly.filter')"
        ></q-select>
      </div>
      <div class="col-auto">
        <q-input
          borderless
          dense
          debounce="300"
          v-model="addressesTable.filter"
          :placeholder="$t('watchonly.search')"
        >
          <template v-slot:append>
            <q-icon name="search"></q-icon>
          </template>
        </q-input>
      </div>
    </div>
    <q-table
      style="height: 400px"
      flat
      dense
      :rows="getFilteredAddresses()"
      row-key="id"
      virtual-scroll
      :columns="addressesTableColumns"
      v-model:pagination="addressesTable.pagination"
      :filter="addressesTable.filter"
    >
      <template v-slot:body="props">
        <q-tr :props="props">
          <q-td auto-width>
            <q-btn
              size="sm"
              color="primary"
              round
              dense
              @click="props.row.expanded = !props.row.expanded"
              :icon="props.row.expanded ? 'remove' : 'add'"
            />
          </q-td>

          <q-td key="address" :props="props">
            <div>
              <a
                style="color: unset"
                :href="
                  'https://' + mempoolEndpoint + '/address/' + props.row.address
                "
                target="_blank"
                v-text="props.row.address"
              ></a>
              <q-badge
                v-if="props.row.branch_index === 1"
                color="primary"
                class="q-mr-md"
                outline
                v-text="$t('watchonly.change')"
              >
              </q-badge>
              <q-btn
                v-if="props.row.gapLimitExceeded"
                color="yellow"
                icon="warning"
                :title="$t('watchonly.gap_limit_exceeded_short')"
                @click="props.row.expanded = !props.row.expanded"
                outline
                class="q-ml-md"
                size="xs"
              >
              </q-btn>
            </div>
          </q-td>

          <q-td
            key="amount"
            :props="props"
            :class="
              props.row.amount > 0 ? 'text-green-13 text-weight-bold' : ''
            "
          >
            <div v-text="satBtc(props.row.amount)"></div>
          </q-td>

          <q-td key="note" :props="props">
            <div v-text="props.row.note"></div>
          </q-td>
          <q-td key="wallet" :props="props">
            <div v-text="getWalletName(props.row.wallet)"></div>
          </q-td>
        </q-tr>
        <q-tr v-show="props.row.expanded" :props="props">
          <q-td colspan="100%">
            <div class="row items-center q-mt-md q-mb-lg">
              <div class="col-2 q-pr-lg"></div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  unelevated
                  dense
                  size="md"
                  icon="qr_code"
                  :color="$q.dark.isActive ? 'grey-7' : 'grey-5'"
                  @click="showAddressDetails(props.row)"
                  v-text="$t('watchonly.qr_code')"
                >
                </q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  color="grey"
                  icon="content_copy"
                  @click="copyText(props.row.address)"
                  class="q-ml-sm"
                  v-text="$t('watchonly.copy')"
                ></q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  dense
                  size="md"
                  icon="refresh"
                  color="grey"
                  @click="scanAddress(props.row)"
                  v-text="$t('watchonly.rescan')"
                >
                </q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  dense
                  size="md"
                  icon="history"
                  color="grey"
                  @click="searchInTab('history', props.row.address)"
                  v-text="$t('watchonly.history')"
                ></q-btn>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  dense
                  size="md"
                  color="grey"
                  @click="searchInTab('utxos', props.row.address)"
                  v-text="$t('watchonly.view_coins')"
                ></q-btn>
              </div>
            </div>

            <div class="row items-center no-wrap q-mb-md">
              <div
                class="col-2 q-pr-lg"
                v-text="$t('watchonly.note_label')"
              ></div>
              <div class="col-8 q-pr-lg">
                <q-input
                  filled
                  dense
                  v-model.trim="props.row.note"
                  type="text"
                  :label="$t('watchonly.note')"
                ></q-input>
              </div>
              <div class="col-2 q-pr-lg">
                <q-btn
                  outline
                  color="grey"
                  @click="updateNoteForAddress(props.row, props.row.note)"
                  v-text="$t('watchonly.update')"
                >
                </q-btn>
              </div>
            </div>

            <div
              v-if="props.row.error"
              class="row items-center no-wrap q-mb-md"
            >
              <div class="col-2 q-pr-lg"></div>
              <div class="col-10 q-pr-lg">
                <q-badge color="red">
                  <span v-text="props.row.error"></span>
                </q-badge>
              </div>
            </div>
            <div
              v-if="props.row.gapLimitExceeded"
              class="row items-center no-wrap q-mb-md"
            >
              <div class="col-2 q-pr-lg"></div>
              <div class="col-10 q-pr-lg">
                <q-badge
                  color="yellow"
                  text-color="black"
                  v-text="$t('watchonly.gap_limit_exceeded')"
                ></q-badge>
              </div>
            </div>
          </q-td>
        </q-tr>
      </template>
    </q-table>
  </div>
</template>

<template id="my-checkbox">
  <div class="checkbox-wrapper" @click="check">
    <div :class="{checkbox: true, checked: checked}"></div>
    <div class="title">{{ title }}</div>
    <q-btn color="primary">XXX</q-btn>
  </div>
</template>

<template id="history">
  <div>
    <div class="row items-center no-wrap q-mb-md">
      <div class="col q-pr-lg"></div>
      <div class="col q-pr-lg">
        <q-input
          borderless
          dense
          debounce="300"
          v-model="filter"
          :placeholder="$t('watchonly.search')"
          class="float-right"
        >
          <template v-slot:append>
            <q-icon name="search"></q-icon>
          </template>
        </q-input>
      </div>
      <div class="col-auto">
        <q-btn outline color="grey" label="...">
          <q-menu auto-close>
            <q-list style="min-width: 100px">
              <q-item clickable>
                <q-item-section
                  @click="exportHistoryToCSV"
                  v-text="$t('watchonly.export_csv')"
                ></q-item-section>
              </q-item>
            </q-list>
          </q-menu>
        </q-btn>
      </div>
    </div>
    <q-table
      style="height: 400px"
      flat
      dense
      :rows="getFilteredAddressesHistory()"
      row-key="id"
      virtual-scroll
      :columns="historyTableColumns"
      :pagination.sync="historyTable.pagination"
      :filter="filter"
    >
      <template v-slot:body="props">
        <q-tr :props="props">
          <q-td auto-width>
            <q-btn
              size="sm"
              color="primary"
              round
              dense
              @click="props.row.expanded = !props.row.expanded"
              :icon="props.row.expanded ? 'remove' : 'add'"
            />
          </q-td>

          <q-td key="status" :props="props">
            <q-badge
              v-if="props.row.sent"
              @click="props.row.expanded = !props.row.expanded"
              color="secondary"
              class="q-mr-md cursor-pointer"
            >
              {{
                props.row.confirmed
                  ? $t('watchonly.sent')
                  : $t('watchonly.sending')
              }}
            </q-badge>
            <q-badge
              v-if="props.row.received"
              @click="props.row.expanded = !props.row.expanded"
              color="primary"
              class="q-mr-md cursor-pointer"
            >
              {{
                props.row.confirmed
                  ? $t('watchonly.received')
                  : $t('watchonly.receiving')
              }}
            </q-badge>
          </q-td>
          <q-td
            key="amount"
            :props="props"
            :class="
              props.row.amount && props.row.received > 0
                ? 'text-green-13 text-weight-bold'
                : ''
            "
          >
            <div>{{ satBtc(props.row.totalAmount || props.row.amount) }}</div>
          </q-td>
          <q-td key="address" :props="props">
            <a
              v-if="!props.row.sameTxItems"
              style="color: unset"
              :href="
                'https://' + mempoolEndpoint + '/address/' + props.row.address
              "
              target="_blank"
            >
              {{ props.row.address }}</a
            >
            <q-badge
              v-if="props.row.sameTxItems"
              @click="props.row.expanded = !props.row.expanded"
              outline
              color="blue"
              class="cursor-pointer"
            >
              ...
            </q-badge>
          </q-td>
          <q-td key="date" :props="props"> {{ props.row.date }} </q-td>
        </q-tr>
        <q-tr v-show="props.row.expanded" :props="props">
          <q-td colspan="100%">
            <div class="row items-center no-wrap q-mb-md">
              <div
                class="col-2 q-pr-lg"
                v-text="$t('watchonly.transaction_id')"
              ></div>
              <div class="col-10 q-pr-lg">
                <a
                  style="color: unset"
                  :href="'https://' + mempoolEndpoint + '/tx/' + props.row.txId"
                  target="_blank"
                >
                  {{ props.row.txId }}</a
                >
              </div>
            </div>
            <div
              v-if="props.row.sameTxItems"
              class="row items-center no-wrap q-mb-md"
            >
              <div class="col-2 q-pr-lg" v-text="$t('watchonly.utxos')"></div>
              <div class="col-4 q-pr-lg">{{ satBtc(props.row.amount) }}</div>
              <div class="col-6 q-pr-lg">{{ props.row.address }}</div>
            </div>
            <div
              v-for="s in props.row.sameTxItems || []"
              class="row items-center no-wrap q-mb-md"
            >
              <div class="col-2 q-pr-lg"></div>
              <div class="col-4 q-pr-lg">{{ satBtc(s.amount) }}</div>
              <div class="col-6 q-pr-lg">{{ s.address }}</div>
            </div>
            <div class="row items-center no-wrap q-mb-md">
              <div class="col-2 q-pr-lg" v-text="$t('watchonly.fee')"></div>
              <div class="col-4 q-pr-lg">{{ satBtc(props.row.fee) }}</div>
            </div>
            <div class="row items-center no-wrap q-mb-md">
              <div
                class="col-2 q-pr-lg"
                v-text="$t('watchonly.block_height')"
              ></div>
              <div class="col-4 q-pr-lg">{{ props.row.height }}</div>
            </div>
          </q-td>
        </q-tr>
      </template>
    </q-table>
  </div>
</template>

<template id="fee-rate">
  <div>
    <div class="row items-center no-wrap q-mb-md">
      <div class="col-2 q-pr-lg" v-text="$t('watchonly.fee_rate_label')"></div>
      <div class="col-3 q-pr-lg">
        <q-input
          filled
          dense
          v-model.number="feeRate"
          step="any"
          :rules="[val => !!val || $t('watchonly.field_required')]"
          type="number"
          label="sats/vbyte"
        ></q-input>
      </div>
      <div class="col-7">
        <q-slider
          v-model="feeRate"
          color="secondary"
          markers
          snap
          label
          label-always
          :label-value="getFeeRateLabel(feeRate)"
          :min="1"
          :max="recommededFees.fastestFee"
        />
      </div>
    </div>
    <div
      v-if="
        feeRate < recommededFees.hourFee || feeRate > recommededFees.fastestFee
      "
      class="row items-center no-wrap q-mb-md"
    >
      <div class="col-2 q-pr-lg"></div>
      <div class="col-10 q-pr-lg">
        <q-badge
          v-if="feeRate < recommededFees.hourFee"
          color="pink"
          size="lg"
          v-text="$t('watchonly.fee_too_low_warning')"
        >
        </q-badge>
        <q-badge
          v-if="feeRate > recommededFees.fastestFee"
          color="pink"
          v-text="$t('watchonly.fee_too_high_warning')"
        >
        </q-badge>
      </div>
    </div>

    <div class="row items-center no-wrap q-mb-md">
      <div class="col-2 q-pr-lg" v-text="$t('watchonly.fee_label')"></div>
      <div class="col-3 q-pr-lg">{{ feeValue }} sats</div>
      <div class="col-7">
        <q-btn
          outline
          dense
          size="md"
          icon="refresh"
          color="grey"
          class="float-right"
          @click="refreshRecommendedFees()"
          v-text="$t('watchonly.refresh_fee_rates')"
        ></q-btn>
      </div>
    </div>
  </div>
</template>

<template id="seed-input">
  <div>
    <div v-if="done">
      <div class="row">
        <div class="col-12" v-text="$t('watchonly.seed_input_done')"></div>
      </div>
    </div>
    <div v-else>
      <div class="row">
        <div class="col-3 q-pt-sm" v-text="$t('watchonly.word_count')"></div>
        <div class="col-6 q-pr-lg">
          <q-select
            filled
            dense
            v-model="wordCount"
            type="number"
            :label="$t('watchonly.word_count')"
            :options="wordCountOptions"
            @input="initWords"
          ></q-select>
        </div>
        <div class="col-3 q-pr-lg"></div>
      </div>
      <div class="row">
        <div class="col-3 q-pr-lg"></div>
        <div
          class="col-6"
          v-text="
            $t('watchonly.enter_word_at_position', {position: actualPosition})
          "
        ></div>
        <div class="col-3 q-pr-lg"></div>
      </div>
      <div class="row">
        <div class="col-3 q-pr-lg">
          <q-btn
            v-if="currentPosition > 0"
            @click="previousPosition"
            unelevated
            class="btn-full"
            color="secondary"
            v-text="$t('watchonly.previous')"
          ></q-btn>
        </div>
        <div class="col-6 q-pr-lg">
          <q-select
            filled
            dense
            use-input
            hide-selected
            fill-input
            input-debounce="0"
            v-model="currentWord"
            :options="options"
            @filter="filterFn"
            @input-value="setModel"
          ></q-select>
        </div>

        <div class="col-3 q-pr-lg">
          <q-btn
            v-if="currentPosition < wordCount - 1"
            @click="nextPosition"
            unelevated
            class="btn-full"
            color="secondary"
            v-text="$t('watchonly.next')"
          ></q-btn>
          <q-btn
            v-else
            @click="seedInputDone"
            unelevated
            class="btn-full"
            color="primary"
            v-text="$t('watchonly.done')"
          ></q-btn>
        </div>
        <q-linear-progress
          :value="currentPosition / (wordCount - 1)"
          size="5px"
          color="primary"
          class="q-mt-sm"
        ></q-linear-progress>
      </div>
    </div>
  </div>
</template>

<template id="send-to">
  <div class="row items-center no-wrap q-mb-md">
    <div class="col-12">
      <q-table
        flat
        dense
        hide-header
        :rows="data"
        :columns="paymentTable.columns"
        :pagination.sync="paymentTable.pagination"
      >
        <template v-slot:body="props">
          <q-tr :props="props">
            <div class="row no-wrap">
              <div class="col-1">
                <q-btn
                  flat
                  dense
                  size="l"
                  @click="deletePaymentAddress(props.row)"
                  icon="cancel"
                  color="grey"
                  class="q-mt-sm"
                ></q-btn>
              </div>
              <div class="col-7 q-pr-lg">
                <q-input
                  filled
                  dense
                  v-model.trim="props.row.address"
                  type="text"
                  :label="$t('watchonly.address_label')"
                  :rules="[val => !!val || $t('watchonly.field_required')]"
                  @input="handleOutputsChange"
                ></q-input>
              </div>
              <div class="col-3 q-pr-lg">
                <q-input
                  filled
                  dense
                  v-model.number="props.row.amount"
                  type="number"
                  step="1"
                  :label="$t('watchonly.amount_sats')"
                  :rules="[
                    val => !!val || $t('watchonly.field_required'),
                    val => +val > DUST_LIMIT || $t('watchonly.amount_too_small')
                  ]"
                  @input="handleOutputsChange"
                ></q-input>
              </div>
              <div class="col-1">
                <q-btn
                  outline
                  color="grey"
                  @click="sendMaxToAddress(props.row)"
                  v-text="$t('watchonly.max')"
                ></q-btn>
              </div>
            </div>
          </q-tr>
        </template>
      </q-table>
      <div class="row items-center no-wrap">
        <div class="col-3 q-pr-lg">
          <q-btn
            unelevated
            color="primary"
            @click="addPaymentAddress"
            class="btn-full"
            v-text="$t('watchonly.add')"
          ></q-btn>
        </div>
        <div class="col-9">
          <div class="float-right">
            <span v-text="$t('watchonly.payed_amount')"></span>
            <span class="text-subtitle2 q-ml-lg">
              {{ satBtc(getTotalPaymentAmount()) }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<template id="payment">
  <div>
    <q-form @submit="checkAndSend" ref="paymentFormRef" class="q-gutter-md">
      <q-card class="q-mt-lg">
        <q-card-section>
          <send-to
            :data.sync="sendToList"
            :fee-rate="feeRate"
            :tx-size="txSize"
            :selected-amount="selectedAmount"
            :sats-denominated="satsDenominated"
            @update:outputs="handleOutputsChange"
          ></send-to>
        </q-card-section>
      </q-card>

      <q-card class="q-mt-lg">
        <q-card-section>
          <div class="row items-center no-wrap">
            <div class="col-4">
              <q-toggle
                :label="$t('watchonly.show_custom_fee')"
                color="primary"
                class="float-left"
                v-model="showCustomFee"
              ></q-toggle>
            </div>

            <div class="col-8">
              <div class="float-right">
                <span v-text="$t('watchonly.fee_rate_label')"></span>
                <span class="text-subtitle2 q-ml-md">
                  {{ feeRate }} sats/vbyte</span
                >
                <span class="q-ml-lg" v-text="$t('watchonly.fee_label')"></span>
                <span class="text-subtitle2 q-ml-md">
                  {{ satBtc(feeValue) }}
                </span>
              </div>
            </div>
          </div>

          <div v-show="showCustomFee" class="row items-center no-wrap q-mt-md">
            <div class="col-12">
              <q-separator class="q-mb-md"></q-separator>
              <fee-rate
                :fee-value="feeValue"
                :rate.sync="feeRate"
                :mempool-endpoint="mempoolEndpoint"
                :sats-denominated="satsDenominated"
              ></fee-rate>
            </div>
          </div>
        </q-card-section>
      </q-card>

      <q-card class="q-mt-lg">
        <q-card-section>
          <div class="row items-center no-wrap">
            <div class="col-4">
              <q-toggle
                :label="$t('watchonly.show_coin_select')"
                color="primary"
                class="float-left"
                v-model="showCoinSelect"
              ></q-toggle>
            </div>

            <div class="col-8">
              <div class="float-right">
                <span v-text="$t('watchonly.balance_label')"></span>
                <span class="text-subtitle2 q-ml-md">
                  {{ satBtc(balance) }}
                </span>
                <span
                  class="q-ml-lg"
                  v-text="$t('watchonly.selected_label')"
                ></span>
                <span class="text-subtitle2 q-ml-md">
                  {{ satBtc(selectedAmount) }}
                </span>
              </div>
            </div>
          </div>

          <div v-show="showCoinSelect" class="row items-center no-wrap q-mt-md">
            <div class="col-12">
              <q-separator class="q-mb-md"></q-separator>
              <utxo-list
                ref="utxoList"
                :utxos="utxos"
                :selectable="true"
                :payed-amount="totalPayedAmount"
                :mempool-endpoint="mempoolEndpoint"
                :sats-denominated="satsDenominated"
                :accounts="accounts"
              ></utxo-list>
            </div>
          </div>
        </q-card-section>
      </q-card>

      <q-card class="q-mt-lg">
        <q-card-section>
          <div class="row items-center no-wrap">
            <div class="col-4">
              <q-toggle
                :label="$t('watchonly.show_change')"
                color="primary"
                class="float-left"
                v-model="showChange"
              ></q-toggle>
            </div>

            <div class="col-4">
              <q-badge
                v-if="changeAmount > 0 && changeAmount < DUST_LIMIT"
                class="text-subtitle2 float-right"
                color="yellow"
                text-color="black"
                v-text="$t('watchonly.below_dust_limit_warning')"
              >
              </q-badge>
            </div>
            <div class="col-4">
              <div class="float-right">
                <span v-text="$t('watchonly.change_label')"></span>
                <span v-if="changeAmount < 0" class="text-subtitle2 q-ml-md">
                  {{ satBtc(0) }}
                </span>
                <span v-if="changeAmount >= 0" class="text-subtitle2 q-ml-md">
                  {{ satBtc(changeAmount) }}
                </span>
              </div>
            </div>
          </div>

          <div v-show="showChange" class="row items-center no-wrap q-mt-md">
            <div class="col-12">
              <q-separator class="q-mb-md"></q-separator>
              <div class="row items-center no-wrap">
                <div
                  class="col-2 q-pr-lg"
                  v-text="$t('watchonly.change_account')"
                ></div>
                <div class="col-3 q-pr-lg">
                  <q-select
                    filled
                    dense
                    emit-value
                    v-model="changeWallet"
                    :options="accounts"
                    @input="selectChangeAddress"
                    :rules="[val => !!val || $t('watchonly.field_required')]"
                    :label="$t('watchonly.wallet_account')"
                  ></q-select>
                </div>
                <div class="col-7">
                  <q-input
                    filled
                    dense
                    readonly
                    v-model.trim="changeAddress.address"
                    :rules="[val => !!val || $t('watchonly.field_required')]"
                    type="text"
                    :label="$t('watchonly.change_address')"
                  ></q-input>
                </div>
              </div>
            </div>
          </div>
        </q-card-section>
      </q-card>

      <div class="row items-center no-wrap q-mb-md q-pt-lg">
        <div class="col-3">
          <q-btn-dropdown
            split
            unelevated
            :disabled="changeAmount < 0 || showChecking"
            :label="$t('watchonly.check_and_send')"
            color="primary"
            type="submit"
            class="btn-full"
          >
            <q-list>
              <q-item :disabled="changeAmount < 0" clickable v-close-popup>
                <q-item-section>
                  <q-item-label
                    v-text="$t('watchonly.serial_port')"
                  ></q-item-label>
                  <q-item-label
                    caption
                    v-text="$t('watchonly.sign_using_serial_port')"
                  >
                  </q-item-label>
                </q-item-section>
              </q-item>
              <q-item @click="showPsbtDialog" clickable v-close-popup>
                <q-item-section>
                  <q-item-label
                    v-text="$t('watchonly.share_psbt')"
                  ></q-item-label>
                  <q-item-label
                    caption
                    v-text="$t('watchonly.share_psbt_desc')"
                  >
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-btn-dropdown>
        </div>

        <div class="col-9">
          <q-spinner
            v-if="showChecking"
            size="2.55em"
            color="primary"
          ></q-spinner>
          <q-badge
            v-if="changeAmount < 0"
            class="text-subtitle2 float-right"
            color="yellow"
            text-color="black"
            v-text="$t('watchonly.payed_amount_higher_warning')"
          >
          </q-badge>
        </div>
      </div>
    </q-form>
    <q-dialog v-model="showPsbt" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <q-input
          filled
          dense
          v-model.trim="psbtBase64"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('watchonly.psbt_label')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('watchonly.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showFinalTx" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <div class="row items-center no-wrap q-mb-sm">
          <div class="col-12">
            <span
              class="text-subtitle1"
              v-text="$t('watchonly.transaction_details')"
            ></span>
          </div>
        </div>
        <q-separator class="q-mb-lg"></q-separator>
        <div v-if="signedTx" class="row items-center no-wrap q-mb-md">
          <div class="col-12">
            <div class="row items-center no-wrap q-mb-sm">
              <div class="col-3 q-pr-lg" v-text="$t('watchonly.version')"></div>
              <div class="col-9">{{ signedTx.version }}</div>
            </div>
            <div class="row items-center no-wrap q-mb-sm">
              <div
                class="col-3 q-pr-lg"
                v-text="$t('watchonly.locktime')"
              ></div>
              <div class="col-9">{{ signedTx.locktime }}</div>
            </div>
            <div class="row items-center no-wrap q-mb-sm">
              <div class="col-3 q-pr-lg" v-text="$t('watchonly.fee')"></div>
              <div class="col-9">
                <q-badge color="orange">{{ satBtc(signedTx.fee) }} </q-badge>
              </div>
            </div>
            <q-separator class="q-mb-lg"></q-separator>
            <span
              class="text-subtitle2"
              v-text="$t('watchonly.outputs')"
            ></span>
            <q-separator class="q-mb-lg"></q-separator>
            <div
              v-for="out in signedTx.outputs"
              class="row items-center no-wrap q-mb-sm"
            >
              <div class="col-3 q-pr-lg">
                <q-badge color="orange">{{ satBtc(out.amount) }}</q-badge>
              </div>

              <div class="col-9">
                <q-badge outline color="blue">{{ out.address }}</q-badge>
              </div>
            </div>
          </div>
        </div>
        <q-separator class="q-mb-lg"></q-separator>
        <div class="row q-mt-lg">
          <div class="col-12">
            <q-input
              filled
              dense
              v-model.trim="signedTxHex"
              type="textarea"
              cols="300"
              rows="1"
              :label="$t('watchonly.signed_tx_hex')"
            ></q-input>
          </div>
        </div>
        <div class="row q-mt-lg">
          <div class="col-12">
            <q-input
              filled
              dense
              v-model.trim="psbtBase64Signed"
              ype="textarea"
              cols="300"
              rows="1"
              :label="$t('watchonly.psbt_label')"
            ></q-input>
          </div>
        </div>

        <div class="row q-mt-lg">
          <q-btn
            unelevated
            color="secondary"
            class="float-left"
            @click="broadcastTransaction"
            v-text="$t('watchonly.send')"
          ></q-btn>
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('watchonly.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="serial-signer">
  <div>
    <q-btn-dropdown
      split
      unelevated
      color="primary"
      icon="usb"
      :text-color="
        selectedPort ? (hww.authenticated ? 'green' : 'orange') : 'white'
      "
      @click="openSerialPortDialog"
    >
      <q-list>
        <q-item
          v-if="selectedPort && !hww.authenticated"
          clickable
          v-close-popup
          @click="hwwShowPasswordDialog()"
        >
          <q-item-section>
            <q-item-label v-text="$t('watchonly.login')"></q-item-label>
            <q-item-label caption v-text="$t('watchonly.enter_password_hww')">
            </q-item-label>
          </q-item-section>
        </q-item>

        <q-item
          v-if="hww.authenticated"
          clickable
          v-close-popup
          @click="hwwLogout()"
        >
          <q-item-section>
            <q-item-label v-text="$t('watchonly.logout')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('watchonly.clear_password_hww')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="!selectedPort"
          clickable
          v-close-popup
          @click="openSerialPortConfig"
        >
          <q-item-section>
            <q-item-label
              v-text="$t('watchonly.config_and_connect')"
            ></q-item-label>
            <q-item-label
              caption
              v-text="$t('watchonly.set_serial_port_params')"
            >
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-for="device in pairedDevices"
          :key="device.id"
          v-if="!selectedPort && showPairedDevices"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label
              @click="openSerialPortConfig(device.id)"
              v-text="
                $t('watchonly.paired_device', {
                  name: device.config.name || 'no-name'
                })
              "
            >
            </q-item-label>
            <q-item-label caption @click="openSerialPortConfig(device.id)"
              >{{ device.id }}
            </q-item-label>
            <q-item-label caption @click="removePairedDevice(device.id)">
              <q-btn
                v-close-popup
                flat
                color="grey"
                class="q-ml-auto"
                v-text="$t('watchonly.forget')"
              ></q-btn>
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="selectedPort"
          clickable
          v-close-popup
          @click="closeSerialPort()"
        >
          <q-item-section>
            <q-item-label v-text="$t('watchonly.disconnect')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('watchonly.disconnect_from_serial')"
            ></q-item-label>
          </q-item-section>
        </q-item>

        <q-item
          v-if="selectedPort"
          clickable
          v-close-popup
          @click="hwwShowRestoreDialog()"
        >
          <q-item-section>
            <q-item-label v-text="$t('watchonly.restore')"></q-item-label>
            <q-item-label caption v-text="$t('watchonly.restore_wallet_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="hww.authenticated"
          clickable
          v-close-popup
          @click="hwwShowSeed()"
        >
          <q-item-section>
            <q-item-label v-text="$t('watchonly.show_seed')"></q-item-label>
            <q-item-label caption v-text="$t('watchonly.show_seed_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="selectedPort"
          @click="hwwShowWipeDialog()"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('watchonly.wipe')"></q-item-label>
            <q-item-label caption v-text="$t('watchonly.wipe_desc')">
            </q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="selectedPort" @click="hwwHelp()" clickable v-close-popup>
          <q-item-section>
            <q-item-label v-text="$t('watchonly.help')"></q-item-label>
            <q-item-label
              caption
              v-text="$t('watchonly.view_commands')"
            ></q-item-label>
          </q-item-section>
        </q-item>
        <q-item
          v-if="selectedPort"
          @click="showConsole = true"
          clickable
          v-close-popup
        >
          <q-item-section>
            <q-item-label v-text="$t('watchonly.console')"></q-item-label>
            <q-item-label caption v-text="$t('watchonly.serial_comm_messages')">
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-btn-dropdown>

    <q-dialog v-model="hww.showConfigDialog" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwConfigAndConnect" class="q-gutter-md">
          <span v-text="$t('watchonly.enter_config')"></span>
          <serial-port-config
            ref="serialPortConfig"
            :config="config"
          ></serial-port-config>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              type="submit"
              v-text="$t('watchonly.connect')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              v-text="$t('watchonly.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showPasswordDialog" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwLogin" class="q-gutter-md">
          <span v-text="$t('watchonly.enter_password_hww_full')"></span>
          <q-input
            filled
            dense
            v-model.trim="hww.password"
            type="password"
            :label="$t('watchonly.password')"
          ></q-input>
          <q-separator></q-separator>
          <q-toggle
            :label="$t('watchonly.passphrase_optional')"
            color="primary"
            v-model="hww.hasPassphrase"
          ></q-toggle>
          <q-input
            v-if="hww.hasPassphrase"
            v-model.trim="hww.passphrase"
            filled
            :type="hww.showPassphrase ? 'text' : 'password'"
            filled
            dense
            :label="$t('watchonly.passphrase')"
          >
            <template v-slot:append>
              <q-icon
                :name="hww.showPassphrase ? 'visibility' : 'visibility_off'"
                class="cursor-pointer"
                @click="hww.showPassphrase = !hww.showPassphrase"
              />
            </template>
          </q-input>

          <br />

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="!selectedPort"
              type="submit"
              v-text="$t('watchonly.login')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              v-text="$t('watchonly.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showConfirmationDialog" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwSignPsbt" class="q-gutter-md">
          <div v-if="tx">
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-12">
                <span class="text-subtitle2"
                  >Output {{ hww.confirm.outputIndex }}</span
                >
                <q-badge
                  v-if="tx.outputs[hww.confirm.outputIndex].branch_index === 1"
                  color="orange"
                  text-color="black"
                >
                  <span v-text="$t('watchonly.change')"></span>
                </q-badge>
              </div>
            </div>
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('watchonly.address_colon')"></span>
              </div>
              <div class="col-9">
                <span>{{ tx.outputs[hww.confirm.outputIndex].address }}</span>
              </div>
            </div>
            <div v-if="!hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('watchonly.amount_label')"></span>
              </div>
              <div class="col-9">
                <span>{{
                  satBtc(tx.outputs[hww.confirm.outputIndex].amount)
                }}</span>
              </div>
            </div>
            <div v-if="hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('watchonly.fee_label')"></span>
              </div>
              <div class="col-9">
                <span>{{ satBtc(tx.feeValue) }}</span>
              </div>
            </div>
            <div v-if="hww.confirm.showFee" class="row q-mt-lg">
              <div class="col-3">
                <span v-text="$t('watchonly.fee_rate_label')"></span>
              </div>
              <div class="col-9">
                <span>{{ tx.feeRate }} sats/vbyte</span>
              </div>
            </div>
          </div>
          <div class="row q-mt-lg">
            <div class="col-12">
              <q-badge class="text-subtitle2" color="yellow" text-color="black">
                <span v-text="$t('watchonly.confirm_check_device')"></span>
              </q-badge>
            </div>
          </div>
          <div class="row q-mt-lg">
            <div class="col-6">
              <q-btn
                v-if="hww.confirm.showFee"
                unelevated
                color="primary"
                :disable="!selectedPort"
                type="submit"
                class="float-left"
                :label="$t('watchonly.confirm')"
              >
                <q-spinner v-if="hww.signingPsbt" color="primary"></q-spinner>
              </q-btn>
            </div>
            <div class="col-3">
              <q-btn
                unelevated
                color="secondary"
                :label="$t('watchonly.next')"
                class="float-left"
                v-if="!hww.confirm.showFee"
                @click="hwwConfirmNext"
              >
              </q-btn>
            </div>
            <div class="col-3">
              <q-btn
                @click="cancelOperation"
                v-close-popup
                flat
                color="grey"
                class="float-right"
                v-text="$t('watchonly.cancel')"
              ></q-btn>
            </div>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showWipeDialog" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwWipe" class="q-gutter-md">
          <q-badge
            color="pink"
            text-color="black"
            v-text="$t('watchonly.wipe_warning')"
          >
          </q-badge>
          <span v-text="$t('watchonly.enter_new_password_hww')"></span>
          <q-input
            filled
            dense
            v-model.trim="hww.password"
            type="password"
            :label="$t('watchonly.password')"
          ></q-input>

          <q-input
            filled
            dense
            v-model.trim="hww.confirmedPassword"
            type="password"
            :label="$t('watchonly.confirm_password')"
          ></q-input>
          <q-badge
            color="pink"
            text-color="black"
            v-text="$t('watchonly.irreversible_warning')"
          >
          </q-badge>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="
                !hww.password ||
                hww.password.length < 8 ||
                hww.password !== hww.confirmedPassword
              "
              type="submit"
              v-text="$t('watchonly.wipe')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              v-text="$t('watchonly.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showConsole" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <q-input
          filled
          dense
          for="serial-port-console"
          v-model.trim="receivedData"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('watchonly.console')"
        ></q-input>

        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('watchonly.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showConsole" position="top">
      <q-card class="q-pa-lg q-pt-xl">
        <div class="row q-mt-lg q-mb-lg">
          <div class="col">
            <q-badge
              class="text-subtitle2 float-right"
              color="yellow"
              text-color="black"
              v-text="$t('watchonly.open_dev_console_warning')"
            >
            </q-badge>
          </div>
        </div>

        <q-input
          filled
          dense
          for="serial-port-console"
          v-model.trim="receivedData"
          type="textarea"
          rows="25"
          cols="200"
          :label="$t('watchonly.console')"
        ></q-input>
        <div class="row q-mt-lg">
          <q-btn
            v-close-popup
            flat
            color="grey"
            class="q-ml-auto"
            v-text="$t('watchonly.close')"
          ></q-btn>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog
      v-model="hww.showSeedDialog"
      @hide="closeSeedDialog"
      position="top"
    >
      <q-card class="q-pa-lg q-pt-xl">
        <span
          v-text="
            $t('watchonly.check_word_position', {
              position: hww.seedWordPosition
            })
          "
        ></span>
        <div class="row q-mt-lg">
          <div class="col-12">
            <q-toggle
              :label="$t('watchonly.show_seed_word')"
              color="primary"
              v-model="hww.showSeedWord"
            ></q-toggle>
          </div>
        </div>
        <div v-if="hww.showSeedWord" class="row q-mt-lg">
          <div class="col-12">
            <q-input readonly v-model.trim="hww.seedWord"></q-input>
          </div>
        </div>

        <div class="row q-mt-lg">
          <div class="col-4">
            <q-btn
              v-if="hww.seedWordPosition !== 1"
              unelevated
              color="primary"
              @click="showPrevSeedWord"
              v-text="$t('watchonly.prev')"
            ></q-btn>
          </div>
          <div class="col-4">
            <q-btn
              v-if="hww.seedWordPosition !== 24"
              unelevated
              color="primary"
              @click="showNextSeedWord"
              v-text="$t('watchonly.next')"
            ></q-btn>
          </div>
          <div class="col-4">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              v-text="$t('watchonly.close')"
            ></q-btn>
          </div>
        </div>
      </q-card>
    </q-dialog>

    <q-dialog v-model="hww.showRestoreDialog" position="top">
      <q-card class="q-pa-lg q-pt-xl lnbits__dialog-card">
        <q-form @submit="hwwRestore" class="q-gutter-md">
          <q-badge
            color="pink"
            text-color="black"
            class="text-subtitle2"
            multi-line
            v-text="$t('watchonly.test_only_warning')"
          >
          </q-badge>
          <br />
          <q-toggle
            :label="$t('watchonly.enter_word_list_space')"
            color="primary"
            v-model="hww.quickMnemonicInput"
          ></q-toggle>
          <br />

          <div v-if="hww.quickMnemonicInput">
            <q-input
              v-model.trim="hww.mnemonic"
              filled
              :type="hww.showMnemonic ? 'text' : 'password'"
              filled
              dense
              :label="$t('watchonly.word_list')"
            >
              <template v-slot:append>
                <q-icon
                  :name="hww.showMnemonic ? 'visibility' : 'visibility_off'"
                  class="cursor-pointer"
                  @click="hww.showMnemonic = !hww.showMnemonic"
                />
              </template>
            </q-input>
          </div>

          <seed-input v-else @on-seed-input-done="seedInputDone"></seed-input>
          <br />
          <q-separator></q-separator>
          <br />
          <span v-text="$t('watchonly.enter_new_password_short')"></span>
          <q-input
            v-model.trim="hww.password"
            filled
            :type="hww.showPassword ? 'text' : 'password'"
            filled
            dense
            :label="$t('watchonly.new_password')"
          >
            <template v-slot:append>
              <q-icon
                :name="hww.showPassword ? 'visibility' : 'visibility_off'"
                class="cursor-pointer"
                @click="hww.showPassword = !hww.showPassword"
              />
            </template>
          </q-input>

          <q-input
            filled
            dense
            v-model.trim="hww.confirmedPassword"
            type="password"
            :label="$t('watchonly.confirm_password')"
          ></q-input>
          <br />
          <q-separator></q-separator>
          <q-badge
            color="pink"
            text-color="black"
            class="text-subtitle2"
            multi-line
            v-text="$t('watchonly.all_data_lost_warning')"
          >
          </q-badge>

          <div class="row q-mt-lg">
            <q-btn
              unelevated
              color="primary"
              :disable="
                !hww.mnemonic ||
                !hww.password ||
                hww.password.length < 8 ||
                hww.password !== hww.confirmedPassword
              "
              type="submit"
              v-text="$t('watchonly.restore')"
            ></q-btn>
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              v-text="$t('watchonly.cancel')"
            ></q-btn>
          </div>
        </q-form>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="trezor-signer">
  <div>
    <q-btn
      @click="connectToDevice"
      split
      unelevated
      color="primary"
      :text-color="connected ? 'green' : ''"
      label="Trezor"
    >
      <q-spinner v-if="isConnecting" color="secondary"></q-spinner>
    </q-btn>

    <q-dialog v-model="showFeatures" position="top">
      <q-card v-if="features" class="q-pa-lg q-pt-md">
        <q-card-section>
          <h5
            v-text="
              $t('watchonly.connected_to_trezor', {
                label: features.payload.label
              })
            "
          ></h5>
          <q-input
            filled
            dense
            for="serial-port-console"
            v-model.trim="featuresJson"
            type="textarea"
            rows="20"
            cols="200"
            :label="$t('watchonly.device_features')"
          ></q-input>
        </q-card-section>

        <q-card-section>
          <div class="row q-mt-lg">
            <q-btn
              v-close-popup
              flat
              color="grey"
              class="q-ml-auto"
              v-text="$t('watchonly.close')"
            ></q-btn>
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>
  </div>
</template>

<template id="serial-port-config">
  <div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.name"
          :label="$t('watchonly.name_optional')"
        ></q-input>
      </div>
    </div>
    <q-separator class="q-mt-sm"></q-separator>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.baudRate"
          type="number"
          :label="$t('watchonly.baud_rate')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.bufferSize"
          type="number"
          :label="$t('watchonly.buffer_size')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.flowControl"
          :label="$t('watchonly.flow_control')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.parity"
          :label="$t('watchonly.parity')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.dataBits"
          type="number"
          :label="$t('watchonly.data_bits')"
        ></q-input>
      </div>
    </div>

    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.stopBits"
          type="number"
          :label="$t('watchonly.stop_bits')"
        ></q-input>
      </div>
    </div>

    <q-separator class="q-mt-sm"></q-separator>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.buttonOnePin"
          :label="$t('watchonly.pin_number_button_1')"
        ></q-input>
      </div>
    </div>
    <div class="row q-mt-md">
      <div class="col-12">
        <q-input
          filled
          dense
          v-model.trim="config.buttonTwoPin"
          :label="$t('watchonly.pin_number_button_2')"
        ></q-input>
      </div>
    </div>
  </div>
</template>

<style>
.btn-full {
  width: 100%;
}
</style>
