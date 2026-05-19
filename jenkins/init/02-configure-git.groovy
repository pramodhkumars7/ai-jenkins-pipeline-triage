#!groovy
import jenkins.model.*

def instance = Jenkins.getInstance()

// Configure Git
def gitConfig = instance.getDescriptor("hudson.plugins.git.GitSCM")
if (gitConfig != null) {
    gitConfig.setGlobalConfigName("Jenkins Local")
    gitConfig.setGlobalConfigEmail("jenkins@local.dev")
    gitConfig.save()
}

println "Git configured for Jenkins"
