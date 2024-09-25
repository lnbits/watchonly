window.app.component('my-checkbox', {
  name: 'my-checkbox',
  template: '#my-checkbox',
  data() {
    return {checked: false, title: 'Check me'}
  },
  methods: {
    check() {
      this.checked = !this.checked
      console.log('### checked', this.checked)
    }
  }
})
