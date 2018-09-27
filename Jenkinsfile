node('worker_node') {
    currentBuild.result = 'SUCCESS'
    // Setup Stash notifications
    step([$class: 'StashNotifier'])

    try {
        stage('Checkout') {
            checkout scm
        }

        stage('Run tests') {
            sh 'make test'
        }

        stage('Parse results') {
            junit 'test*.xml'
        }

    }
    catch (Exception e) {
        echo "Exception Caught: ${e.getMessage()}"
        currentBuild.result = 'FAILURE'
        // want to collect and parse test results so we get a nice notification on hipchat
        junit 'test*.xml'
    } 
    finally {
        step([$class: 'StashNotifier'])

        stage('Clean') {
            sh 'make clean'
            sh 'docker system prune -f'
            deleteDir()
        }
    }
}
