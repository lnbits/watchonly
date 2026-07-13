window.app.component('history', {
  name: 'history',
  template: '#history',

  props: ['history', 'mempool-endpoint', 'sats-denominated', 'filter'],
  data: function () {
    return {
      historyTable: {
        pagination: {
          rowsPerPage: 0
        }
      }
    }
  },

  computed: {
    historyTableColumns() {
      return [
        {
          name: 'expand',
          align: 'left',
          label: ''
        },
        {
          name: 'status',
          align: 'left',
          label: this.$t('watchonly.status')
        },
        {
          name: 'amount',
          align: 'left',
          label: this.$t('watchonly.amount'),
          field: 'amount',
          sortable: true
        },
        {
          name: 'address',
          align: 'left',
          label: this.$t('watchonly.address_label'),
          field: 'address',
          sortable: true
        },
        {
          name: 'date',
          align: 'left',
          label: this.$t('watchonly.date'),
          field: 'date',
          sortable: true
        },
        {
          name: 'txId',
          field: 'txId'
        }
      ]
    },
    historyExportColumns() {
      return [
        {
          label: this.$t('watchonly.action'),
          field: 'action'
        },
        {
          label: this.$t('watchonly.date_time'),
          field: 'date'
        },
        {
          label: this.$t('watchonly.amount'),
          field: 'amount'
        },
        {
          label: this.$t('watchonly.fee'),
          field: 'fee'
        },
        {
          label: this.$t('watchonly.transaction_id'),
          field: 'txId'
        }
      ]
    }
  },

  methods: {
    satBtc(val, showUnit = true) {
      return satOrBtc(val, showUnit, this.satsDenominated)
    },
    getFilteredAddressesHistory: function () {
      return this.history.filter(a => (!a.isChange || a.sent) && !a.isSubItem)
    },
    exportHistoryToCSV: function () {
      const history = this.getFilteredAddressesHistory().map(a => ({
        ...a,
        action: a.sent ? 'Sent' : 'Received'
      }))
      LNbits.utils.exportCSV(
        this.historyExportColumns,
        history,
        'address-history'
      )
    }
  },
  created: async function () {}
})
